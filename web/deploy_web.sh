#!/bin/bash
# Build the live app page with the API URL + map key and publish it as the site's index.html
set -euo pipefail
cd "$(dirname "$0")/.."
API=$(cat backend/build/api_url.txt)
KEY=$(grep '^AMAZON_LOCATION_API_KEY=' .env | head -1 | cut -d= -f2- | tr -d "\"' ")
python3 tools/build_web.py "$API" "$KEY" us-east-1
# safety: refuse to publish a page whose script doesn't parse
if command -v node >/dev/null; then
  python3 -c "import re;open('/tmp/breath_loader.js','w').write(re.findall(r'<script>(.*?)</script>',open('web/index.html').read(),re.S)[-1])"
  node --check /tmp/breath_loader.js || { echo "index.html script has a syntax error - not uploading"; exit 1; }
fi
aws s3 cp web/index.html s3://breath-site-sitebucket-viisucftcf27/index.html --content-type "text/html; charset=utf-8" --cache-control max-age=60
echo "Live: https://d28nym7zkli7me.cloudfront.net/"
