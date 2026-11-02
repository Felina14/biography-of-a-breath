#!/bin/bash
# Allow the Journey API and the AgentCore narrator to call Amazon Nova Pro (still Amazon Nova, via Bedrock).
set -euo pipefail
REGION=us-east-1; ACCT=$(aws sts get-caller-identity --query Account --output text)
APIFN=$(aws cloudformation describe-stack-resources --stack-name breath-backend --region $REGION --query "StackResources[?LogicalResourceId=='ApiFunction'].PhysicalResourceId" --output text)
APIROLE=$(aws lambda get-function-configuration --function-name $APIFN --region $REGION --query Role --output text | awk -F/ '{print $NF}')
DOC="{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"bedrock:InvokeModel\",\"bedrock:InvokeModelWithResponseStream\"],\"Resource\":[\"arn:aws:bedrock:*::foundation-model/amazon.nova-pro-v1:0\",\"arn:aws:bedrock:$REGION:$ACCT:inference-profile/us.amazon.nova-pro-v1:0\"]}]}"
for R in $APIROLE breath-agentcore-runtime-role; do aws iam put-role-policy --role-name $R --policy-name nova-pro --policy-document "$DOC" && echo "granted Nova Pro to $R"; done
