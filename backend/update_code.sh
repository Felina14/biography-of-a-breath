#!/bin/bash
# Fast code-only update for both Lambdas (keeps the already-built dependency folders), then re-ingest, redeploy web, smoke-test.
set -euo pipefail
cd "$(dirname "$0")/.."
REGION=us-east-1; STACK=breath-backend
ACCT=$(aws sts get-caller-identity --query Account --output text); ART=breath-artifacts-$ACCT
out() { aws cloudformation describe-stacks --stack-name $STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
INGEST=$(out IngestFunction); API_URL=$(out ApiUrl)
APIFN=$(aws cloudformation describe-stack-resources --stack-name $STACK --region $REGION --query "StackResources[?LogicalResourceId=='ApiFunction'].PhysicalResourceId" --output text)
[ -d backend/build/api/numpy ] && [ -d backend/build/ingest/numpy ] || { echo "build folders missing - run bash backend/deploy.sh instead"; exit 1; }
python3 -m py_compile backend/api/app.py backend/ingest/app.py
cp backend/api/app.py backend/api/countries.json backend/build/api/ && cp backend/ingest/app.py backend/build/ingest/
PKGS="api ingest"; [ "${API_ONLY:-0}" = 1 ] && PKGS="api"
for f in $PKGS; do rm -f backend/build/$f.zip; (cd backend/build/$f && zip -qr ../$f.zip .); aws s3 cp --quiet backend/build/$f.zip s3://$ART/code/$f.zip; done
[ "${API_ONLY:-0}" = 1 ] || aws lambda update-function-code --function-name $INGEST --s3-bucket $ART --s3-key code/ingest.zip --region $REGION --query LastModified --output text
aws lambda update-function-code --function-name $APIFN --s3-bucket $ART --s3-key code/api.zip --region $REGION --query LastModified --output text
[ "${API_ONLY:-0}" = 1 ] || aws lambda wait function-updated --function-name $INGEST --region $REGION; aws lambda wait function-updated --function-name $APIFN --region $REGION
if [ "${API_ONLY:-0}" != 1 ]; then echo "Re-ingesting (2-6 min)..."
aws lambda invoke --function-name $INGEST --region $REGION --cli-read-timeout 900 /tmp/ingest.json >/dev/null && cat /tmp/ingest.json; echo; fi
bash web/deploy_web.sh
aws cloudfront create-invalidation --distribution-id EE8KFWZ79FX7Z --paths "/*" --query Invalidation.Status --output text || true
for d in back forward; do
  curl -s "${API_URL}?lat=30.9&lon=75.85&level=10&dir=$d" | python3 -c "
import sys,json;d=json.load(sys.stdin);P=d['points']
print('$d', d.get('direction'), d['name'], round(d['total_km']),'km | stops:',[s['name']+' ('+s.get('country_name','?')+')' for s in d.get('places',[])][:5])
print('  new fields present:', all(k in P[0] for k in ('gust_kmh','visibility_km','snowfall','near','hazards')),
      '| gust sample', P[len(P)//2].get('gust_kmh'), '| vis', P[len(P)//2].get('visibility_km'), '| near', P[len(P)//2].get('near'))
print('  hazards on path:', sorted({h for p in P for h in p['hazards']}) or 'none', '| downwind:', (d.get('downwind') or {}).get('towns') if isinstance(d.get('downwind'),dict) else len(d.get('downwind') or []))"
done
echo "Narration test (forward, Ludhiana)..."
curl -s --max-time 60 "${API_URL%/}/narrate?lat=30.9&lon=75.85&level=10&dir=forward" | python3 -c "
import sys,json;d=json.load(sys.stdin)
for t in d.get('agent_trace',[]):
  if t.get('tool')=='tell_story': print('  tell_story: rejected',t['rejected'],[r['reason'] for r in t['reviewer']])
for l in d.get('lines',[]): print('  ',round(72-l['hours_ago']),'h |',l['text'])"
