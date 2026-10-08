#!/usr/bin/env sh
# Packages the source (no node_modules, build output, caches, local data, secrets or git history) into reloop-hackathon.zip
set -eu
cd "$(dirname "$0")/.."
rm -f reloop-hackathon.zip
zip -rq reloop-hackathon.zip . -x ".env" ".venv/*" "*/node_modules/*" "frontend/dist/*" ".data" ".data/*" "*/.data" "*/.data/*" "*/.aws-sam/*" "samconfig.toml" "*__pycache__*" "*.pyc" "*/.pytest_cache/*" ".git/*" ".DS_Store" "reloop-hackathon.zip"
echo "wrote $(pwd)/reloop-hackathon.zip"
