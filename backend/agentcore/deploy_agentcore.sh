#!/bin/bash
# Deploy Puff (the narrator agent) to Amazon Bedrock AgentCore Runtime and point the Journey API at it.
# Run from the project root:  bash backend/agentcore/deploy_agentcore.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
REGION=us-east-1; STACK=breath-backend; NAME=breath_narrator; ROLE=breath-agentcore-runtime-role
ACCT=$(aws sts get-caller-identity --query Account --output text)
out() { aws cloudformation describe-stacks --stack-name $STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
BUCKET=$(out DataBucket); API_URL=$(out ApiUrl)
APIFN=$(aws cloudformation describe-stack-resources --stack-name $STACK --region $REGION --query "StackResources[?LogicalResourceId=='ApiFunction'].PhysicalResourceId" --output text)
APIROLE=$(aws lambda get-function-configuration --function-name $APIFN --region $REGION --query Role --output text | awk -F/ '{print $NF}')
echo "== 1/6 runtime execution role ($ROLE)"
TRUST=$(cat <<J
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"bedrock-agentcore.amazonaws.com"},"Action":"sts:AssumeRole",
 "Condition":{"StringEquals":{"aws:SourceAccount":"$ACCT"},"ArnLike":{"aws:SourceArn":"arn:aws:bedrock-agentcore:$REGION:$ACCT:*"}}}]}
J
)
if ! aws iam get-role --role-name $ROLE >/dev/null 2>&1; then
  aws iam create-role --role-name $ROLE --assume-role-policy-document "$TRUST" --description "Biography of a Breath narrator on AgentCore Runtime" >/dev/null
  echo "   created; waiting for IAM to propagate"; sleep 15
fi
aws iam put-role-policy --role-name $ROLE --policy-name breath-narrator --policy-document "$(cat <<J
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],"Resource":["arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0","arn:aws:bedrock:$REGION:$ACCT:inference-profile/us.amazon.nova-lite-v1:0"]},
 {"Effect":"Allow","Action":"polly:SynthesizeSpeech","Resource":"*"},
 {"Effect":"Allow","Action":"geo-places:ReverseGeocode","Resource":"arn:aws:geo-places:$REGION::provider/default"},
 {"Effect":"Allow","Action":"s3:GetObject","Resource":"arn:aws:s3:::$BUCKET/*"},
 {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents","logs:DescribeLogStreams"],"Resource":"arn:aws:logs:$REGION:$ACCT:log-group:/aws/bedrock-agentcore/runtimes/*"},
 {"Effect":"Allow","Action":"logs:DescribeLogGroups","Resource":"arn:aws:logs:$REGION:$ACCT:log-group:*"},
 {"Effect":"Allow","Action":["xray:PutTraceSegments","xray:PutTelemetryRecords","xray:GetSamplingRules","xray:GetSamplingTargets"],"Resource":"*"},
 {"Effect":"Allow","Action":"cloudwatch:PutMetricData","Resource":"*","Condition":{"StringEquals":{"cloudwatch:namespace":"bedrock-agentcore"}}},
 {"Effect":"Allow","Action":["ecr:BatchGetImage","ecr:GetDownloadUrlForLayer"],"Resource":"arn:aws:ecr:$REGION:$ACCT:repository/*"},
 {"Effect":"Allow","Action":"ecr:GetAuthorizationToken","Resource":"*"}]}
J
)"
echo "== 2/6 stage agent source"
B=backend/agentcore/build; rm -rf $B; mkdir -p $B
cp backend/agentcore/agent.py backend/agentcore/requirements.txt backend/api/app.py backend/api/countries.json $B/
printf '{"DATA_BUCKET": "%s"}\n' "$BUCKET" > $B/breath_config.json
echo "== 3/6 AgentCore starter toolkit"
[ -x backend/agentcore/.venv-tk/bin/agentcore ] || { python3 -m venv backend/agentcore/.venv-tk && backend/agentcore/.venv-tk/bin/pip install -q -U pip bedrock-agentcore-starter-toolkit; }
AC=$PWD/backend/agentcore/.venv-tk/bin/agentcore
echo "== 4/6 configure + deploy to AgentCore Runtime (direct code deploy, Python 3.12)"
( cd $B
  $AC configure -e agent.py -n $NAME -er arn:aws:iam::$ACCT:role/$ROLE -rf requirements.txt -r $REGION -dt direct_code_deploy -rt PYTHON_3_12 --disable-memory -ni
  $AC deploy --auto-update-on-conflict --env DATA_BUCKET=$BUCKET )
ARN=$(aws bedrock-agentcore-control list-agent-runtimes --region $REGION --query "agentRuntimes[?agentRuntimeName=='$NAME'].agentRuntimeArn | [0]" --output text)
echo "   runtime: $ARN"
[ -n "$ARN" ] && [ "$ARN" != "None" ] || { echo "runtime ARN not found"; exit 1; }
echo "== 5/6 let the Journey API invoke the runtime (role $APIROLE, function $APIFN)"
aws iam put-role-policy --role-name $APIROLE --policy-name invoke-agentcore-narrator --policy-document \
  "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"bedrock-agentcore:InvokeAgentRuntime\",\"Resource\":[\"$ARN\",\"$ARN/*\"]}]}"
ENV=$(aws lambda get-function-configuration --function-name $APIFN --region $REGION --query Environment.Variables --output json | python3 -c "import sys,json;v=json.load(sys.stdin) or {};v['AGENT_RUNTIME_ARN']='$ARN';print(json.dumps({'Variables':v}))")
aws lambda update-function-configuration --function-name $APIFN --region $REGION --timeout 120 --environment "$ENV" --query LastModified --output text
aws lambda wait function-updated --function-name $APIFN --region $REGION
sleep 10
echo "== 6/6 end-to-end test: website API -> AgentCore Runtime -> Nova + Polly"
S=$(date +%s)
curl -s --max-time 120 "${API_URL%/}/narrate?lat=13.11&lon=80.16&level=10" | python3 -c "
import sys,json;d=json.load(sys.stdin)
print('   served_by:',d.get('served_by','Lambda (fallback)'),'| runtime s:',d.get('runtime_seconds'),'| lines:',len(d.get('lines',[])))
[print('    ',l.get('half'),round(72-l['hours_ago']),'h |',l['text'][:110]) for l in d.get('lines',[])]"
echo "   total $(( $(date +%s)-S )) s"
echo "Done. Note: CloudFormation parameter AgentRuntimeArn=$ARN keeps this wiring if you later run backend/deploy.sh with --parameter-overrides."
