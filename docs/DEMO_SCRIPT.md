# 3-minute demo script

**Story:** *Akarsh has an old laptop in a drawer. ReLoop turns that into a decision, an action, a reward and a measurable change for his building.*
**Rule of the hackathon:** the video must **show AWS**, not just name it. Record against the deployed stack (CloudFront URL), never `localhost`.

## Before you hit record (checklist)
1. **Deploy and seed** ([README → Deploy to AWS](../README.md#deploy-to-aws)). The header badge must say **Running on AWS**.
2. **Check Bedrock works** for your account/region: do one scan and confirm the *Under the hood* panel says `bedrock`, not `mock`. If it shows the amber "Live AI is unavailable" notice, fix model access first.
3. **Rehearse with a throwaway resident**, not Akarsh. The check changes the account it runs as, and the story below (tier crossing, rank jump) only happens once for `demo@reloop.app`:
   ```bash
   python scripts/e2e_demo.py --base <ApiUrl> --register --email rehearsal@example.com --password 'Str0ng#Pass1' --staff-password '<DemoPassword>' --real-ops
   ```
   This also warms the Lambda and Bedrock (the first call after idle is the slow one).
4. Photograph a **real old laptop** with your phone (better than the sample illustration for a real vision model). Have the sample as a backup.
5. Pre-open these console tabs, logged in, in the stack region: **CloudWatch → Logs → Live Tail** (`/aws/lambda/reloop-demo-api`), **S3** (uploads bucket), **DynamoDB → Explore items** (table `reloop-demo`), **Cognito → user pool → Groups**, **API Gateway** or **CloudFront**. Hide anything showing secrets (Lambda environment variables list the demo password).
6. Be signed in as **Akarsh** on the dashboard, with a pre-filled address ready to paste: `Room 214, Hostel Block A, SVNIT`.
7. Retakes: the second time, Akarsh is already past the tier; speak to the numbers **on screen**, not the ones in this script. For an exact repeat, deploy a fresh stack.

Numbers below are from a fresh local seed with the mock AI (`+194 points`, rank `#17 → #8`, `Advocate → Steward`, building score `71.7 → 72.1`). With real Bedrock the item, confidence and condition may differ; your numbers will vary by a few points.

## Run sheet
| Time | On screen | Say | Do | AWS shown |
|---|---|---|---|---|
| **0:00–0:20** Problem | Dashboard as Akarsh. The **Your next best action** card is visible. | "Akarsh has an old laptop in a drawer. He doesn't know what it's worth, whether to sell or recycle it, where to take it, or whether it matters at all. ReLoop closes that loop: scan it, decide, act, and see the impact." | Open on the landing hero for 3 s, cut to the dashboard. | None yet. |
| **0:20–0:55** Scan | **Scan** → *Take or choose a photo* on the phone (or the *Laptop* sample). The five-step analysis screen. | "He opens WasteLens and takes a photo. One request goes to Lambda, which asks Amazon Bedrock to read the image, then a Strands agent runs seven tools: price, recyclers, impact, points, history and a recommendation." | Photo → wait on the analysis screen. | **Split screen:** CloudWatch Live Tail showing the `waste_submission` JSON event arrive (`"provider": "bedrock"`). |
| **0:55–1:20** AI result + value | The result card: *Likely identified*, **AI estimate** chip, confidence bar, value range, weight, CO₂e, recommended action. Then **Correct result**. | "Laptop, ninety-one percent sure, worth an estimated six to twenty-two thousand rupees if it works. It's labeled an estimate, not an offer. But the screen is cracked, so Akarsh corrects the condition: the recommendation flips from resell to recycle and the numbers update." | **Correct result → Condition: Damaged → Update estimate** (this also confirms the item) **→ Recycle.** | Open the header badge: **Under the hood** (model id, agent mode, table, S3 object key, Lambda request id); then 3 s on the S3 object and the DynamoDB item. |
| **1:20–1:45** Recycler + pickup | **Find recycler** (distance-sorted list, *Demo data* notice, schematic map) → **Schedule pickup** → wizard. | "ReLoop shows the nearest recyclers with distance, accepted items and pickup minimums. These are labeled demo data. He books a pickup for tomorrow morning: items, address, time, confirm." | Click the first card's **Schedule pickup**, paste the address, pick a slot, **Confirm request**. | DynamoDB `pickup_requests` item (status `requested`). |
| **1:45–2:10** Rewards + leaderboard | **Simulate collection and verification** → the **reward** card → **Leaderboard**. | "A collector weighs and verifies it. Only now do points land: one hundred ninety-four, from a documented formula. One point eight kilograms diverted, about six point four kilograms of CO₂e avoided, labeled as an estimate. Akarsh jumps from seventeenth to eighth and reaches a new tier." | Click the demo shortcut (say it's standing in for the collector; the *Operations* page shows the real steps). Open **How these points were calculated** for 2 s. Go to **Leaderboard**. | DynamoDB `points_ledger` row (+194, breakdown in `meta`). |
| **2:10–2:35** Building dashboard | **Building and campus**: ReLoop Score, *How it was calculated*, the collected-vs-expected chart, the **Next best action** card. | "His hostel's ReLoop Score moves from seventy-one point seven to seventy-two point one, and the score shows exactly how it's calculated. The challenge moved too. And the dashboard turns data into a next step: small electronics are falling behind, so run a collection drive." | Scroll to the gap chart and the drive card. | None (keep the pace). |
| **2:35–2:50** Advisor | **Advisor** → quick prompt **How can my building improve?** → *Verified data* + *AI-generated recommendation*. | "The Advisor only answers from this data. Verified facts on top, with sources; the generated recommendation below, labeled. Small electronics are the biggest gap, so a charger drive could close it." | One tap on the prompt. | The card says *Written by Amazon Bedrock from the data above*. |
| **2:50–3:00** AWS + impact | Architecture diagram (`docs/ARCHITECTURE.md`) over the Cognito groups / API Gateway tabs. End card: *ReLoop. Every insight leads to an action.* | "Built on Bedrock, Strands agents, Lambda, API Gateway, DynamoDB, S3, Cognito and CloudFront. ReLoop: every insight leads to an action." | Cut to the diagram. | Cognito user pool with its four groups; API Gateway or CloudFront. |

## Minimum AWS proof (if you must cut)
The **Under the hood** panel + **CloudWatch Live Tail** during the scan + the **S3 object** + the **DynamoDB item**. Together they show Bedrock, Lambda, S3 and DynamoDB serving one real request.

## If something goes wrong on camera
- **Bedrock slow (>8 s):** keep talking over the analysis screen; it's real latency. Don't fake it.
- **AI misidentifies the item:** perfect. Say "the AI isn't always right, so the person confirms," and use **Correct result**.
- **The amber "Live AI is unavailable" notice:** stop, fix model access, retake. Don't record the fallback as if it were Bedrock.
- **Duplicate-photo hold appears:** you reused a photo another account already submitted. Use a fresh photo.

## Optional 20-second add-ons (only if you have time)
Operations (collector queue, **Verify and award points** with a weighed 1.7 kg), the fraud queue (*Suspicious submission detected*), the AI accuracy card (*correct on first attempt 87%*).
