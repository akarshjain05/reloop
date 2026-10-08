# AWS cost and clean-up

Designed for hackathon traffic: everything is pay-per-use or free to hold, nothing runs 24/7. **This page gives no prices**: they change and vary by region, so check the AWS pricing pages and your account's current free-tier or credit terms.

## What costs money, roughly in order
| Service | Why it is the cost driver | Demo-scale expectation |
|---|---|---|
| **Bedrock** | Billed per input/output token. One scan = one image + prompt for classification, plus (with the Strands agent) a few short tool-calling turns. The Advisor adds a short call per question. | A few hundred scans/questions for rehearsal and recording is small with a Nova-class model. Switch to a larger model only if you need to. |
| **Lambda** | GB-seconds. 1024 MB, ~1 s typical; the first call after idle is slower (cold start with the large dependency set). | Negligible. |
| **DynamoDB (on-demand)** | Read units. **Dashboards read whole entity kinds** (e.g. all submissions, ledger rows and impact rows) because leaderboards/scores are computed on read. With the full demo dataset (4,828 documents) our *estimate from item sizes* is several hundred read units per dashboard load (not measured on AWS). | Cents for a demo; do not point a large audience at it without materialising leaderboards (see ARCHITECTURE → Scaling). |
| **CloudFront / S3** | Data transfer and requests for a ~0.5 MB site; uploads are small (client resizes to ≤1280 px). | Negligible. |
| **API Gateway / Cognito / CloudWatch Logs** | Per request / monthly active users / log ingestion and storage (14-day retention). | Negligible at this scale. |

No NAT gateways, load balancers, provisioned capacity, RDS, or always-on compute are used.

## Guard rails to set up before you deploy
1. **AWS Budgets** alert at a small amount (billing console → Budgets → Create budget), emailed to the whole team.
2. Keep `DemoMode=true` **only** on a short-lived stack. It exposes demo credentials and a one-click "award points" shortcut.
3. API Gateway throttling is already set (burst 50, 25 req/s). Lower it if you share the URL widely.
4. S3 uploads expire after 30 days (lifecycle rule); logs after 14 days.

## Shutting everything down
```bash
STACK=reloop-demo; REGION=ap-south-1
# 1) empty both buckets (CloudFormation cannot delete non-empty buckets)
for K in UploadsBucketName FrontendBucketName; do
  B=$(aws cloudformation describe-stacks --stack-name $STACK --region $REGION --query "Stacks[0].Outputs[?OutputKey=='$K'].OutputValue" --output text)
  aws s3 rm "s3://$B" --recursive --region $REGION
done
# 2) delete the stack: Lambda, API, table, buckets, Cognito pool, log group, CloudFront (CloudFront takes a few minutes)
cd infrastructure && sam delete --stack-name $STACK --region $REGION
```
Bedrock has no standing resources, so nothing to remove there. Afterwards, check the Billing console the next day for stragglers, and confirm the CloudFormation stack is gone in every region you used (the stack region and `BedrockRegion` may differ; only the stack region holds resources).

## Running cheaper while developing
Develop and rehearse in **demo mode** (no AWS calls at all). Switch to AWS only for the integration check and the recording. `AI_PROVIDER=bedrock` lets you try real Bedrock from your laptop while keeping everything else local.
