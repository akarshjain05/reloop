# ReLoop: hackathon submission (Waste and Energy track)

*Tagline:* **Turn waste into value.**

## Problem
Old phones, laptops, chargers and power banks pile up in drawers because people can't answer four questions: what is it worth, should I sell or recycle it, where do I take it, and did it matter? What isn't kept goes to bins and informal channels, where hazardous batteries and recoverable metals are lost. Buildings, campuses and offices can't see what their people do with e-waste, so they can't steer it. India publishes lists of authorised recyclers, but they live in PDFs, not in an app a resident would open.

## Target users
- **Residents and students** (the daily user): want a quick, trustworthy answer and a small reward.
- **Collectors and recycler staff:** need a clear queue and a way to record verified weights.
- **Campus, society and office admins:** want a measurable score, the biggest collection gap, and a concrete campaign to run.
- **Platform admins:** need verification, abuse review and honest metrics (including how often the AI is wrong).

## Solution
A loop that always ends in an action: **photograph → AI identifies → person confirms → value, impact and a decision → pickup or drop-off → verified → points, leaderboard, building score → what to do next.** The central screen, WasteLens, answers *what is this, what is it worth, what should I do, where should I take it, and what will I gain.*

## What changes for people
| Who | Before | After |
|---|---|---|
| Resident | An unknown device in a drawer | A decision in under a minute (resell / repair / recycle / donate), a nearby recycler or a pickup slot, and points once it's verified |
| Building | A vague recycling target | A ReLoop Score with its calculation, the category falling behind (e.g. small electronics), and a sized collection drive |
| Collector | Phone calls and notes | One queue; verify with a measured weight; the award, rank and score update immediately |
| Admin | No visibility | Verification, a fraud review queue, AI accuracy feedback, CSV exports, an audit log |

## AI
- **WasteLens (Amazon Bedrock, Converse API, image input):** identifies the item with confidence, brand, condition and quantity under a strict JSON contract, validated server-side. Output is labeled *AI estimate*, and the person confirms or corrects; predictions and corrections are stored.
- **Triage agent (Strands Agents SDK):** seven tools (identify, price, recyclers, impact, points, history, recommend). The model chooses the order; every number comes from a tool and each call is shown in a trace. The same tools run as a fixed pipeline when Bedrock is unavailable.
- **Scan My Waste:** flags e-waste and hazardous items in a bin; the person removes them and confirms, which raises the building's segregation score.
- **ReLoop Advisor:** answers only from the app's own records; verified facts (with sources) are shown separately from the generated recommendation.
- **Decisions are rules, not vibes:** resell/repair/recycle/donate comes from explainable rules (batteries are always recycle-only).

## AWS
Amazon Bedrock (vision, agent, advisor), Strands Agents SDK, Lambda (the whole FastAPI app via Mangum), API Gateway (HTTP API with throttling), DynamoDB (single table, on-demand), S3 (private uploads with signed URLs; static site), CloudFront (OAC, HTTPS), Cognito (sign-in, role groups), CloudWatch Logs (structured JSON), IAM (least privilege), CloudFormation/SAM. In-app, an **Under the hood** panel prints the model id, table, S3 object key and Lambda request id for the user's own request. Service-by-service detail: [AWS_USAGE.md](AWS_USAGE.md). SQS/EventBridge were deliberately left out.

## Environmental impact
Impact is reported as **estimates from configured assumptions**: kilograms diverted (collector-weighed when available), illustrative CO₂e, and recoverable material by type. The assumption files are plain YAML to be replaced with cited factors. The honest claim is behavioural: the product turns an unused device into a verified recycling action and makes the community's progress and gaps visible. It does not claim audited tonnage or carbon savings.

## Technical architecture
React + TypeScript + Vite + Tailwind on S3/CloudFront → API Gateway → Lambda (FastAPI) → DynamoDB / S3 / Bedrock / Cognito. One backend serves both local and AWS runs; providers (`AIProvider`, `Store`, `ImageStorage`, `AuthProvider`, `PriceProvider`, notification `Channel`) swap between demo and AWS. Diagrams, data model, state machine and formulas: [ARCHITECTURE.md](ARCHITECTURE.md).

## Innovation
1. **Insight → action as a product rule:** every dashboard number ends in a button (Next Best Action, collection-gap drive sizing, pickup-vs-drop-off advice).
2. **Human-in-the-loop AI with a measured correction rate** reported to admins.
3. **Points that can't be farmed:** paid only after verified handover; bonuses scale with item value so splitting items gains nothing; duplicate-photo detection (exact and perceptual), cooldown, velocity, daily cap, held awards with admin review.
4. **A score that shows its working:** the ReLoop Score exposes five components and the formula.
5. **An agent whose numbers are tool-derived,** with a visible trace, and a graceful fixed-pipeline fallback.
6. **Demo mode that is the production code path,** so judges can use it without an AWS account.

## Responsible AI
Estimate labels everywhere; confidence shown; confirm/correct before recording; price and CO₂e disclaimers; fictional recyclers labeled *Demo data* and never called authorised; no live-price claims; EXIF/GPS stripped; private storage with expiring URLs; transparent, adjustable assumptions; plain-language failure states; admin audit log. Limits are listed in the README.

## Scalability
Serverless and on-demand: Lambda scales per request, DynamoDB is pay-per-request. Known limits (documented): leaderboards and scores are computed on read; one DynamoDB partition per entity kind; synchronous AI call within API Gateway's 29 s. The path to scale is materialised leaderboards (DynamoDB Streams), queue-based analysis with status polling (SQS), GSIs for time ranges.

## Future roadmap
Import real authorised-recycler data (CPCB / state boards) with geocoding via Amazon Location Service and a real map; live refurbisher price APIs behind `PriceProvider`; resale/donation partners so reuse can earn verified points; email/SMS/push channels; WhatsApp scanning; EPR-certificate and producer-take-back integrations; multilingual UI; materialised analytics and CloudWatch dashboards.

## How it maps to the judging criteria
| Criterion | Evidence |
|---|---|
| Real environmental problem | E-waste and hazardous batteries in drawers and bins; recyclers hard to find |
| What actually changes for people | Decision + action + reward in one flow; Next Best Action on every dashboard; building gap → sized campaign |
| AWS usage | Bedrock, Strands, Lambda, API Gateway, DynamoDB, S3, CloudFront, Cognito, CloudWatch, IAM, SAM; *Under the hood* panel; [AWS_USAGE.md](AWS_USAGE.md) |
| Design and usability | Mobile-first, one-tap scan, honest labels, empty/loading/error states, accessible markup (axe-audited structure) |
| Working execution | 69 backend tests, 42 frontend tests, the whole story runs over real HTTP (`scripts/e2e_demo.py`); moto-emulated AWS stack |
| 3-minute demo | [DEMO_SCRIPT.md](DEMO_SCRIPT.md) |

## Verification status (be upfront with judges)
Verified locally: tests, build, end-to-end story over HTTP (including real collector/admin steps), emulated DynamoDB/S3/Cognito, the real Lambda handler with API Gateway events, the real Strands SDK loop with a scripted model, cfn-lint. **To verify on your AWS account before submitting:** deploy, real Bedrock responses, how a live model drives the agent, Cognito token verification, CloudFront. See README → Known limitations.

## Provenance (fill in before submitting)
- **Built during the event:** _list the work done in the event window, matching your commit history_
- **Third-party libraries, fonts, icons:** [THIRD_PARTY.md](../THIRD_PARTY.md). No starter template or boilerplate repository was used.
- **AI assistance:** _describe how AI coding tools were used, as the hackathon rules require_
