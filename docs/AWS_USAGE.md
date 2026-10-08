# AWS usage

The hackathon requires that the project **uses AWS and that the demo video shows it**. This page lists each service, why it is there, where it is in the code, and what to show on camera. Services were added only where they do real work.

> **Verification status.** Each AWS-facing code path is covered by tests against the **moto emulator**, fake clients, or (for the agent) the real Strands SDK driven by a scripted model, and the template is cfn-lint clean. None of it has been exercised against live AWS yet. Deploy once and run `python scripts/e2e_demo.py --base <ApiUrl>` before relying on any claim below in a video. See README → *Known limitations*.

| Service | Why | Where in the code |
|---|---|---|
| **Amazon Bedrock** (Converse API) | Multimodal photo understanding (`WasteLens`, `Scan My Waste`) and the model that writes Advisor recommendations and the agent's rationale. | `backend/app/ai/bedrock.py` (`BedrockProvider.analyze_item / analyze_bin / chat`), `backend/app/services/advisor.py` |
| **Strands Agents SDK** (AWS open source) on Bedrock | The triage workflow is a genuine tool-using agent: seven tools, the model chooses the order. Falls back to the same tools in a fixed order. | `backend/app/ai/agent.py` (`build_tools`, `_run_strands`, `run_workflow`) |
| **AWS Lambda** | Runs the entire FastAPI app (Mangum adapter): no servers, scales to zero. | `backend/app/lambda_handler.py`, `infrastructure/template.yaml` → `ApiFunction` |
| **Amazon API Gateway** (HTTP API) | Public HTTPS entry point with built-in throttling (burst 50, 25 req/s). | `infrastructure/template.yaml` → `HttpApi` |
| **Amazon DynamoDB** | System of record: users, submissions, AI predictions, points ledger, impact, pickups, challenges, audit log (on-demand, encrypted, one GSI). | `backend/app/repositories/dynamo.py`, `template.yaml` → `Table` |
| **Amazon S3** (uploads) | Private bucket for scan photos (SSE, 30-day lifecycle); the app returns **signed, expiring** URLs. | `backend/app/services/storage.py` (`S3Storage`), `template.yaml` → `UploadsBucket` |
| **Amazon S3 + CloudFront** (site) | Hosts the React build; private bucket reached through Origin Access Control, HTTPS only, SPA fallback. | `template.yaml` → `FrontendBucket`, `Distribution`; `scripts/deploy_frontend.sh` |
| **Amazon Cognito** | Email/password sign-in; roles are **user pool groups** (`USER`, `COLLECTOR`, `ADMIN`, `ORGANIZATION_ADMIN`) read from the ID token. | `backend/app/core/security.py` (`CognitoAuth`), `template.yaml` → `UserPool*`, `Group*` |
| **Amazon CloudWatch Logs** | Structured JSON events (submissions, pickup transitions, audits, AI fallbacks); 14-day retention. | `backend/app/core/logging.py`, `template.yaml` → `ApiLogGroup` |
| **AWS IAM** | Least privilege: table + bucket scoped policies, `bedrock:InvokeModel` on foundation models/inference profiles only, Cognito admin actions on **this pool only**. | `template.yaml` → `ApiFunction.Policies` (asserted in `backend/tests/test_infrastructure.py`) |
| **AWS CloudFormation / SAM** | One-command reproducible deployment. | `infrastructure/template.yaml`, `samconfig.toml.example` |

**Deliberately not used:** SQS, EventBridge, Amplify, Amazon Location Service. Nothing consumes queue/event traffic yet, the analysis fits one request, and the site is simple static hosting. They are in the roadmap (Location Service for geocoding imported recycler lists and a real map).

## What happens in the demo, end to end
1. **Sign in:** the browser calls `POST /auth/login` → API Gateway → Lambda → Cognito `InitiateAuth`. The ID token's `cognito:groups` decides the role.
2. **Scan:** the photo goes to Lambda; it is validated, re-encoded (EXIF/GPS stripped), hashed, checked for duplicates, then the agent calls **Bedrock** for vision and runs the other tools. The image is written to **S3**; submission and prediction to **DynamoDB**; a `waste_submission` JSON event goes to **CloudWatch**.
3. **Confirm/correct:** `POST /waste/confirm` re-estimates and stores the correction in DynamoDB (this is what the AI accuracy metric reads).
4. **Pickup → verify:** state changes are DynamoDB writes; verification writes impact and ledger rows and a `pickup_status` + `audit` event to CloudWatch.
5. **Advisor:** facts are read from DynamoDB; Bedrock writes the recommendation text.

## Showing it in the video
The in-app **"Under the hood"** panel (header badge → *Running on AWS*) prints values straight from the API response: model id, Bedrock region, agent mode, DynamoDB table, S3 bucket and object key, Lambda request id, and total time. Pair it with consoles:

| Moment | On screen | What it proves |
|---|---|---|
| During the scan | CloudWatch → Logs → **Live Tail** on `/aws/lambda/reloop-demo-api` showing a `waste_submission` event (`"provider": "bedrock"`) | Lambda + Bedrock + structured logging |
| After the result | App **Under the hood** panel, then **S3** → uploads bucket → `uploads/<user>/<id>.jpg` | Bedrock model id, signed storage |
| After confirm/pickup | **DynamoDB** → Explore items → table `reloop-demo` (`pk = waste_submissions` or `pickup_requests`) | The record is in DynamoDB |
| After verification | DynamoDB `points_ledger` row with the breakdown in `meta` | Auditable points |
| Closing | `docs/ARCHITECTURE.md` diagram, Cognito user pool (groups), API Gateway/CloudFront | The architecture, not just the app |

Do not show secrets: the Lambda *Configuration → Environment variables* page lists the demo password. Full run sheet: [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
