#!/usr/bin/env sh
# Builds the frontend against the deployed API and publishes it to S3 + CloudFront.
#   sh scripts/deploy_frontend.sh [stack-name] [region]
set -eu
STACK="${1:-reloop-demo}"
REGION="${2:-${AWS_REGION:-ap-south-1}}"
out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
API=$(out ApiUrl); BUCKET=$(out FrontendBucketName); DIST=$(out DistributionId); SITE=$(out FrontendUrl)
echo "API:    $API"
echo "Bucket: $BUCKET"
cd "$(dirname "$0")/../frontend"
npm ci --no-audit --no-fund
VITE_API_BASE_URL="$API" npm run build
aws s3 sync dist "s3://$BUCKET" --delete --region "$REGION"
echo "Published: $SITE"
