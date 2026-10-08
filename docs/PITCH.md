# Pitch

## One sentence
ReLoop turns the old laptop in your drawer into a decision, a pickup, a reward and a measurable change for your building, in about a minute.

## 30 seconds
"Everyone has an old laptop or a drawer of chargers. You don't know what it's worth, whether to sell or recycle it, or where to take it. With ReLoop you take a photo. AI tells you what it is and what it's roughly worth, you correct it if it's wrong, and ReLoop says: recycle it, and here is the nearest drop-off or a pickup tomorrow. Once a collector verifies it you earn points, your building's score moves, and the app tells your community which category to collect next. Every number is labeled as an estimate, and every insight ends in a button."

## 2 minutes
"Meet Akarsh. He has a cracked laptop in his hostel room. Like most people, he's stuck on four questions: what's it worth, sell or recycle, where does it go, and does it even matter.

He opens ReLoop and takes a photo. Behind that one request, Amazon Bedrock reads the image and a Strands agent runs seven tools: price, nearby recyclers, environmental impact, points, his history, and a recommendation. ReLoop says: laptop, about ninety percent sure, worth roughly six to twenty-two thousand rupees *if* it works, clearly labeled an estimate. The screen is cracked, so he corrects the condition, the recommendation flips from resell to recycle, and the estimate updates. The AI didn't get the last word; he did, and we record that correction.

He sees the nearest recyclers with distance and pickup minimums, labeled demo data, and books a pickup for tomorrow. When a collector weighs and verifies it, points land from a formula he can read: a hundred and ninety-four. He moves from seventeenth to eighth on the leaderboard and reaches a new tier. We estimate 1.8 kilograms diverted and about six kilograms of CO₂e avoided, and we say plainly that's an estimate.

Then the community effect. His hostel's ReLoop Score goes up, and the score shows how it's calculated. The dashboard doesn't stop at a number: it says small electronics are the biggest uncollected category and sizes a collection drive to close the gap. The Advisor says the same, with verified facts on top and generated advice below, each labeled.

And it resists gaming: duplicate photos are caught, awards for flagged items are held for review, and nothing pays out without a verified handover.

It runs on Bedrock, Lambda, DynamoDB, S3, Cognito and CloudFront, and the whole thing also runs offline in demo mode. ReLoop: every insight leads to an action."

## Why now
Phones and laptops are replaced every few years, recycler lists exist but live in PDFs, and vision models can finally identify an item from a phone photo cheaply enough to put the answer in a person's hand at the moment they're holding the device.

## Why this is different
- **It ends in a verified action,** not a map or a chart. Rewards require a verified handover.
- **The AI is honest:** labeled estimates, a confidence bar, a person who confirms, and a correction rate we report.
- **Insights come with next steps:** a collection gap becomes a sized campaign.
- **A transparent score and formula,** not a decorative number.
- **Anti-abuse by design,** not as an afterthought.

## Why AWS
Bedrock gives one multimodal API for vision and advice without hosting models; Strands gives a real tool-using agent from the same ecosystem; Lambda + API Gateway + DynamoDB + S3 scale to zero and cost almost nothing between demos; Cognito gives role-based sign-in via groups; CloudFront serves the site. The in-app *Under the hood* panel shows these services serving the user's own request.

## What the judges should remember
1. A photo becomes a decision, a pickup, a reward and a building-level change in one flow.
2. The AI proposes, the person confirms, and the product says what is an estimate.
3. Every dashboard insight ends in an action; the building's biggest gap becomes a campaign.
4. It's real: AWS services serve the request on camera, and the same code also runs offline.
