#!/bin/bash
# Push new narrator code to the existing AgentCore runtime (keeps role, cached dependencies and wiring).
set -euo pipefail
cd "$(dirname "$0")/../.."
B=backend/agentcore/build; AC=$PWD/backend/agentcore/.venv-tk/bin/agentcore
[ -f $B/.bedrock_agentcore.yaml ] && [ -x $AC ] || { echo "run backend/agentcore/deploy_agentcore.sh first"; exit 1; }
python3 -m py_compile backend/api/app.py backend/agentcore/agent.py
cp backend/agentcore/agent.py backend/api/app.py backend/api/countries.json $B/
BUCKET=$(python3 -c "import json;print(json.load(open('$B/breath_config.json'))['DATA_BUCKET'])")
export AGENTCORE_SUPPRESS_RECOMMENDATION=1
( cd $B && $AC deploy --auto-update-on-conflict --env DATA_BUCKET=$BUCKET )
API_URL=$(aws cloudformation describe-stacks --stack-name breath-backend --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
sleep 15
for q in "lat=30.9&lon=75.85&level=10" "lat=13.11&lon=80.16&level=10"; do S=$(date +%s)
curl -s --max-time 120 "${API_URL%/}/narrate?$q" | python3 -c "
import sys,json;d=json.load(sys.stdin)
print('served_by:',d.get('served_by','Lambda (fallback)'),'| runtime s:',d.get('runtime_seconds'),'| lines:',len(d.get('lines',[])),'| retries:',sum(1 for t in d.get('agent_trace',[]) if t.get('tool')=='model_retry'))
[print('  ',l.get('half'),round(72-l['hours_ago']),'h |',l['text']) for l in d.get('lines',[])]"
echo "--- $(( $(date +%s)-S )) s"; done
