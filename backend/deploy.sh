#!/bin/bash
# Deploy the live backend. Run from the project root:  bash backend/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
REGION=us-east-1; STACK=breath-backend
ACCT=$(aws sts get-caller-identity --query Account --output text)
ART=breath-artifacts-$ACCT
aws s3api head-bucket --bucket $ART 2>/dev/null || aws s3 mb s3://$ART --region $REGION
rm -rf backend/build && mkdir -p backend/build/api backend/build/ingest
PIP="python3 -m pip install -q --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --python-version 3.12 --implementation cp --only-binary=:all: --upgrade"
$PIP --target backend/build/api numpy
$PIP --target backend/build/ingest numpy eccodes eccodeslib
# trim to stay under the 250 MB Lambda limit (CLI tools, headers, cmake files, tests are not needed at runtime)
( cd backend/build/ingest && rm -rf eccodeslib/bin eccodeslib/include eccodeslib/cmake eccodeslib/lib64/cmake eccodeslib/lib64/pkgconfig \
    eckitlib/bin eckitlib/include eckitlib/lib64/cmake eckitlib/lib64/pkgconfig bin numpy/*/tests numpy/tests && find . -name __pycache__ -prune -exec rm -rf {} + )
( cd backend/build/api && rm -rf bin numpy/*/tests numpy/tests && find . -name __pycache__ -prune -exec rm -rf {} + )
echo "ingest package: $(du -sh backend/build/ingest | cut -f1)  api package: $(du -sh backend/build/api | cut -f1)"
cp backend/api/app.py backend/api/countries.json backend/build/api/ && cp backend/ingest/app.py backend/build/ingest/
aws cloudformation package --template-file backend/template.yaml --s3-bucket $ART --output-template-file backend/build/packaged.yaml --region $REGION >/dev/null
RUNTIME_ARN=$(aws bedrock-agentcore-control list-agent-runtimes --region $REGION --query "agentRuntimes[?agentRuntimeName=='breath_narrator'].agentRuntimeArn | [0]" --output text 2>/dev/null || true); [ "$RUNTIME_ARN" = "None" ] && RUNTIME_ARN=""
aws cloudformation deploy --template-file backend/build/packaged.yaml --stack-name $STACK --capabilities CAPABILITY_IAM --region $REGION --parameter-overrides AgentRuntimeArn="$RUNTIME_ARN"
out() { aws cloudformation describe-stacks --stack-name $STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
BUCKET=$(out DataBucket); API=$(out ApiUrl); FN=$(out IngestFunction)
aws s3 cp ref/regions.npz s3://$BUCKET/ref/regions.npz
aws s3 cp ref/places.npz s3://$BUCKET/ref/places.npz
echo "Running first ingest (2-5 min)..."
aws lambda invoke --function-name $FN --region $REGION --cli-read-timeout 900 /tmp/ingest.json >/dev/null && cat /tmp/ingest.json; echo
echo "API: $API"
curl -s "${API}?lat=51.5074&lon=-0.1278" | python3 -c "import sys,json;d=json.load(sys.stdin);print('London ->',d.get('name'),d.get('total_km'),'km,',len(d.get('places',[])),'stops,',[e['text'] for e in d.get('events',[])][:4])"
echo "$API" > backend/build/api_url.txt
