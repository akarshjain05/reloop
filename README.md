# ReLoop

## Turn waste into value.

ReLoop helps people do the right thing with old electronics. Photograph a device, confirm what the AI saw, get an **estimated** resale/recycling value, a clear decision (resell, repair, recycle or donate), a nearby recycler or a pickup slot, and points once a collector **verifies** the handover. Every verified item moves a building's ReLoop Score, a leaderboard and a CO₂e estimate, and an Advisor tells you what to do next.

Built for the **Waste and Energy** track: *close the loop on what a city throws away.* The question behind every screen is **"What does the user do differently because of this?"**

> **Status, honestly.** Everything below runs locally with no AWS account (demo mode) and is covered by automated tests. The AWS path (Bedrock, Strands agent, Cognito, DynamoDB, S3, Lambda, CloudFront) is implemented and tested against the **moto emulator and unit tests**, and the SAM template is **lint-clean**, but it has **not been deployed or run against live AWS** by the person who generated this repo (no credentials). See [Known limitations](#known-limitations) and do the 20-minute [deploy and verify](#deploy-to-aws) before you record, because the hackathon requires the demo video to **show** AWS.

```text
DISCOVER → SCAN → UNDERSTAND → VALUE → CHOOSE → ACT → VERIFY → REWARD → MEASURE → COMMUNITY IMPROVES
```

## Contents
[Problem](#problem) · [Solution](#solution) · [Key features](#key-features) · [Quick start](#quick-start-local-no-aws-needed) · [Demo mode](#demo-mode) · [Environment variables](#environment-variables) · [Architecture](#architecture) · [Deploy to AWS](#deploy-to-aws) · [Testing](#testing) · [Responsible AI](#responsible-ai) · [Known limitations](#known-limitations) · [Project structure](#project-structure) · [Team](#team-contribution) · [Credits](#open-source-credits)

## Problem
People keep dead laptops, phones, chargers and power banks in drawers because they can't answer four questions: *What is it worth? Should I sell or recycle it? Where do I take it? Did it actually matter?* Informal collection loses valuable material and sends hazardous parts (batteries) to landfill and bins. Buildings and campuses have no way to see, or steer, what their residents do with e-waste.

## Solution
A loop that ends in a verified action, not a dashboard:

1. **WasteLens** photo scan: the AI identifies the item, with a confidence score and an honest *AI estimate* label.
2. **Human in the loop**: the person confirms or corrects item, brand, condition, quantity and weight; estimates update and the correction is recorded (it feeds an AI accuracy metric).
3. **Decision**: explainable rules pick resell / repair / recycle / donate with a one-line reason (batteries are always recycle-only).
4. **Act**: nearby recyclers (distance, accepted items, pickup minimums, verification label) or a four-step pickup/drop-off flow.
5. **Verify → reward**: a collector weighs and verifies; points are written to a **ledger**, impact is recorded, challenges, leaderboards and the building's **ReLoop Score** update.
6. **Advisor + Next Best Action**: recommendations grounded in your own records, with verified facts kept separate from generated text.

**Why it matters:** the user's next step is always one tap away, and the community can see exactly which category (e.g. small electronics) is falling behind and what a collection drive would add.

## Key features
| Area | What's built |
|---|---|
| **WasteLens** | Photo → AI identification → value, weight, CO₂e, points, recommendation. Camera capture on mobile, client-side resize, sample photos for judges. Correct-the-AI form. Agent trace ("what ReLoop's agent did"). |
| **Scan My Waste** | Photograph a bin; AI flags e-waste/hazardous items; the person removes them and confirms; the building's segregation score rises. |
| **ReLoop Exchange** | 14 curated demo models with estimated resale/recycle ranges and a recommended action, filterable. Clearly labeled *estimated local market range, not live prices*. |
| **Find a Recycler** | 8 fictional demo recyclers, distance-sorted, filters, schematic map (works with no map API), directions link, "Demo data" labeling. |
| **Pickups** | Items → Address → Time → Confirm; drop-off mode with a code; statuses *Requested → Scheduled → Collector assigned → Picked up → Verified → Recycled*. |
| **Points** | Transparent formula with a ledger row per change, daily cap, tiers with positive "N more points to reach X" messaging. |
| **Leaderboards** | Global, Campus, Building, Neighborhood; last 30 days or all time. |
| **Challenges** | E-Waste Week, 100 Chargers, Campus Cleanup; progress moves on verified items only; joined challenges add a capped bonus. |
| **ReLoop Score** | 0–100 per building/campus from five measured components, shown with its calculation. |
| **Next Best Action** | Rule-based, estimate-labeled, always ends in a button. |
| **ReLoop Advisor** | Intent router over the app's own data; Bedrock writes the recommendation when available; verified facts always shown separately with sources. |
| **Fraud protection** | Exact + perceptual duplicate photo detection, submission cooldown, velocity check, held points + admin review queue, daily cap, EXIF/GPS stripped. |
| **Operations** | Collector queue, verify-with-weight, fraud review, AI classification inspection, analytics (incl. AI correction rate), users, CSV export (formula-injection safe), recycler management, audit log. |
| **Under the hood** | A header badge opens a panel showing, from the live API response, which AWS services served your request (model id, table, bucket/object key, Lambda request id). |

## Quick start (local, no AWS needed)
Requires Python 3.10+ (tested on 3.12) and Node 18+ (tested on 22).

```bash
git clone <your-repo-url> reloop && cd reloop

# Terminal 1: API  (http://localhost:8000, docs at /docs)
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2: web app  (http://localhost:5173)
cd frontend && npm install && npm run dev
```
`make setup`, `make backend` and `make frontend` do the same. `docker compose up` is also provided (written but not run by the author; use the commands above if it misbehaves).

Open http://localhost:5173 → **Sign in** → pick **Resident (Akarsh)**. Try the sample photos on the Scan page, or upload your own.

Run the whole story headlessly (also a good pre-recording check): `make e2e` or `python scripts/e2e_demo.py --base http://localhost:8000 [--real-ops]`.

### Demo accounts (fictional data, local/demo mode only)
| Email | Role | Password |
|---|---|---|
| `demo@reloop.app` | Resident ("Akarsh") | `ReLoop#Demo1` |
| `org@reloop.app` | Campus admin (ORGANIZATION_ADMIN) | `ReLoop#Demo1` |
| `collector@reloop.app` | Collector | `ReLoop#Demo1` |
| `admin@reloop.app` | Platform admin | `ReLoop#Demo1` |

The password is a documented demo value. Set `DEMO_MODE=false` (and use Cognito) for anything real; `APP_ENV=production` refuses to start dev auth with the default JWT secret.

## Demo mode
With no configuration the app uses an **in-memory store**, **local disk** for images, **dev auth** and a **deterministic mock AI**, seeded with 4,828 fictional documents (54 people in 6 buildings across 3 organizations, six months of history, a live pickup queue, a fraud queue, 3 challenges) so charts are never empty.

The mock AI is **not computer vision**: it derives its answer from the file name (`laptop.jpg`, `power-bank.jpg`) or a hash of the image, and says so in the UI. Real photos need Bedrock (`AI_PROVIDER=bedrock`). If AWS is configured but unavailable, the app says so and either falls back to demo estimates (demo mode) or lets the person choose the item manually.

## Environment variables
See [`.env.example`](.env.example). All optional locally.

| Variable | Purpose |
|---|---|
| `DEMO_MODE` | Demo accounts on the login page, demo fast-forward button, auto-seeding of the in-memory store |
| `AWS_REGION`, `BEDROCK_REGION`, `BEDROCK_MODEL_ID` | Where the API lives, where the Bedrock model is enabled, and which multimodal model to use |
| `DYNAMODB_TABLE`, `S3_BUCKET`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` | Switch each layer from local to AWS when set |
| `AI_PROVIDER`, `STORE_BACKEND`, `STORAGE_BACKEND`, `AUTH_PROVIDER` | `auto` / explicit overrides (`auto` = AWS when configured or running in Lambda) |
| `USE_STRANDS` | Drive the tools with the Strands Agents SDK when Bedrock is the provider |
| `CURRENCY_SYMBOL`, `LOCALE`, `WEIGHT_UNIT`, `COUNTRY` | i18n-ready defaults: India / INR / kg |

Never commit secrets: `.env` is git-ignored and the SAM stack injects configuration into Lambda.

## Architecture
```text
React + Vite ──► CloudFront / S3 ──► API Gateway (HTTP API) ──► Lambda (FastAPI via Mangum)
                                                                   ├─► DynamoDB   (single table)
                                                                   ├─► S3         (images, signed URLs)
                                                                   ├─► Bedrock    (vision + Strands agent)
                                                                   └─► Cognito    (sign-in, role groups)
                                  CloudWatch: structured JSON logs from the app
```
**One backend, two ways to run it.** The same FastAPI app runs under uvicorn locally and under Lambda through Mangum, so there is no second implementation to drift and the local demo is the same code path as production. Providers (`AIProvider`, `Store`, `ImageStorage`, `AuthProvider`, `PriceProvider`, notification `Channel`) hide the difference between demo and AWS. Details, diagrams and the points/impact/score formulas: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**AI architecture.** `AIProvider` has `MockProvider` and `BedrockProvider` (Converse API, image input, strict JSON contract validated server-side). A **triage agent** exposes seven tools (`identify_waste`, `get_price_estimate`, `get_recycler_options`, `calculate_environmental_impact`, `calculate_points`, `get_user_history`, `recommend_next_action`). With Bedrock a **Strands Agents SDK** agent chooses the tool order and writes a two-sentence rationale; without it the *same tools* run as a fixed pipeline. Every number comes from a tool, never from free-form model text, and each call is shown in a trace. The ReLoop Advisor only answers from the app's data.

**AWS usage, service by service, with file paths:** [docs/AWS_USAGE.md](docs/AWS_USAGE.md).

## Deploy to AWS
Prerequisites: AWS account, AWS CLI configured, [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) (`brew install aws-sam-cli`), Python 3.12, Node 18+. **Bedrock:** make sure the model in `BedrockModelId` can be invoked in `BedrockRegion` from your account (Bedrock console; the default is an Amazon Nova multimodal model, and any Converse-capable model with image input and tool use works).

```bash
cd infrastructure
cp samconfig.toml.example samconfig.toml        # edit region / Bedrock region / model if needed
sam build && sam deploy                          # first time: sam deploy --guided

# note the outputs, then seed demo data + the four demo sign-ins into DynamoDB and Cognito
cd .. && python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt
python scripts/seed_demo.py --table reloop-demo --region ap-south-1 --pool <UserPoolId>

# build the site against the deployed API and publish it to S3 + CloudFront
sh scripts/deploy_frontend.sh reloop-demo ap-south-1
```
Open the `FrontendUrl` output. Check **Header badge → "Running on AWS"** and run `python scripts/e2e_demo.py --base <ApiUrl>` as a smoke test. The demo video must be recorded against this deployment, not `localhost`: see the AWS checklist in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). Teardown and cost control: [docs/AWS_COST.md](docs/AWS_COST.md). Template validity: `make lint-template` (cfn-lint) passes.

## Testing
```bash
cd backend && pytest -q                    # 69 tests (+1 slow emulator test: pytest -m slow)
cd frontend && npm test                    # 42 tests
cd frontend && npm run build               # type-check + production build
make lint-template                         # cfn-lint on the SAM template
make e2e                                   # the demo story over real HTTP (server must be running)
```
Backend tests cover points, impact, pricing, classification (mock and Bedrock response parsing), duplicate detection, cooldown, pickup transitions and permissions, the API journey, admin protection, and run the **whole app on emulated DynamoDB + S3 + Cognito (moto)**, through the **real Lambda handler with API Gateway events**, and through the **real Strands Agents SDK loop driven by a scripted fake model** (tool dispatch, skipped tools, drifting arguments, failure fallback). Frontend tests replay **real API responses captured from the backend** (`scripts/capture_fixtures.py`) through every page, drive the scan → correct → confirm → pickup → reward journey, and run an **axe-core structural accessibility audit** (colour contrast needs a real browser and is not covered).

## Responsible AI
- Every AI- or assumption-derived number is labeled (*AI estimate*, *estimated range, not a guaranteed offer*, *illustrative CO₂e*).
- The person confirms or corrects before anything is recorded; predictions, confidence and corrections are stored and the **correction rate** is reported to admins.
- Prices come from a curated demo dataset behind a `PriceProvider` interface; nothing claims live market data. Recyclers are fictional and labeled *Demo data*; nothing claims official authorisation.
- Points need a **verified** handover. Duplicate photos, velocity and daily caps protect against farming; flagged awards are *held*, never silently dropped.
- Failures are explained in plain language and never block the flow (AI down → pick the item manually).
- Photos are re-encoded and stripped of EXIF/GPS before storage; S3 objects are private with signed, expiring URLs.

## Known limitations
Read these before you present; they are the honest edges of what was built and verified.
- **Not run on live AWS.** No credentials were available. Verified: unit tests, moto emulation of DynamoDB/S3/Cognito, the real Lambda handler with synthetic API Gateway events, cfn-lint. **Not verified:** `sam deploy`, real Bedrock responses (including whether a real model chooses sensible tool calls; the agent loop itself is tested against the real SDK with a scripted model), Cognito JWKS signature verification, CloudFront. Budget time to fix surprises (model IDs and access vary by account and region).
- **UI was never opened in a browser** (none in the build sandbox). It is type-checked, built, tested with 42 tests and an axe audit, and every page renders against real payloads, but visual polish, responsive layout on a phone and colour contrast are unverified. Open it on a phone and a laptop first and fix what looks off. Screenshots below are placeholders for that reason.
- The demo AI is a mock keyed off file names/hashes. Sample photos are illustrations; a real vision model may be less sure about them than about a real photo.
- Prices, impact factors, expected category mix and recycler data are **placeholders**, not measured or verified data (see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)).
- ReLoop Exchange shows estimates only: no listings, offers or sales.
- The map is schematic (no map API). Leaderboards and scores are computed on read from the ledger, fine for thousands of rows, but would be materialised at scale. DynamoDB uses one partition per entity kind (a hot-partition risk at scale).
- Cognito sign-up creates confirmed users without email verification (acceptable for a demo, not for production). The in-app rate limiter is per Lambda container; the API Gateway throttle is the real control.
- `DEMO_MODE=true` exposes demo credentials and a fast-forward that awards points instantly. Turn it off for real use.
- SQS and EventBridge are intentionally **not** used: nothing consumes those events yet, and adding services only to list them would be dishonest. Notifications are in-app only (the `Channel` interface is ready for email/SMS/push).
- Currency/locale/units are configurable, but a few server-written sentences contain `₹`.
- `docker-compose.yml` was written but not executed.

## Project structure
```text
backend/            FastAPI app (also the Lambda code): app/{api,services,ai,repositories,core,data}, tests/
  app/data/         assumptions (impact factors, scoring) and curated demo data: edit these, no code changes needed
frontend/           React + TypeScript + Vite + Tailwind; src/{pages,components,lib,test}
infrastructure/     template.yaml (AWS SAM) and samconfig.toml.example
scripts/            seed_demo.py, deploy_frontend.sh, e2e_demo.py, capture_fixtures.py, make_sample_images.py, make_zip.sh
docs/               ARCHITECTURE, AWS_USAGE, AWS_COST, DATA_SOURCES, DEMO_SCRIPT, HACKATHON_SUBMISSION, PITCH
```
(The brief suggested a root `data/` folder. Data lives under `backend/app/data/` so it is packaged into the Lambda zip.)

## Screenshots
_Placeholders: capture these from a running instance (the build sandbox had no browser)._
`docs/img/landing.png` · `docs/img/dashboard.png` · `docs/img/scan-result.png` · `docs/img/pickup-reward.png` · `docs/img/org-score.png` · `docs/img/under-the-hood.png`

## Team contribution
_Fill in before submitting. Judges score what was added during the event, so keep real commit history._

| Name | Role | What they built |
|---|---|---|
| _name_ | _role_ | _e.g. scan flow, Bedrock integration_ |
| _name_ | _role_ | _e.g. SAM deployment, demo video_ |

## Open-source credits
See [THIRD_PARTY.md](THIRD_PARTY.md). Licensed under MIT ([LICENSE](LICENSE)).
