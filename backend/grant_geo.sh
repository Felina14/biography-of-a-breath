#!/bin/bash
# Allow the Journey API and the AgentCore narrator to call Amazon Location ReverseGeocode (settlement names along the path).
set -euo pipefail
REGION=us-east-1
APIFN=$(aws cloudformation describe-stack-resources --stack-name breath-backend --region $REGION --query "StackResources[?LogicalResourceId=='ApiFunction'].PhysicalResourceId" --output text)
APIROLE=$(aws lambda get-function-configuration --function-name $APIFN --region $REGION --query Role --output text | awk -F/ '{print $NF}')
DOC="{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"geo-places:ReverseGeocode\",\"Resource\":\"arn:aws:geo-places:$REGION::provider/default\"}]}"
for R in $APIROLE breath-agentcore-runtime-role; do aws iam put-role-policy --role-name $R --policy-name reverse-geocode --policy-document "$DOC" && echo "granted ReverseGeocode to $R"; done
