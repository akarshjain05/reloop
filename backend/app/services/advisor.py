"""ReLoop Advisor — grounded in the app's own records. Verified facts come from the data; the recommendation
text is generated (by Bedrock when available, by rules otherwise) and is always labelled as such."""
from __future__ import annotations

import json
import re

from ..ai.types import AIUnavailable
from ..core.logging import log_event
from ..models import kinds as K
from . import challenges as chl
from .actions import recommend_action
from .catalog import category_label, category_of, detect_item_type, item_info
from .dashboard import next_best_action
from .impact import compute_impact
from .leaderboard import rank_of
from .orgscore import gap_analysis, reloop_score
from .points import compute_points, tier_for
from .recyclers import nearby, user_location
from .stats import Snapshot, dates_by_user, since_window, streak_weeks, totals

S_REC, S_BLD, S_CAT, S_DIR, S_CFG = ("Your verified ReLoop records", "Building statistics", "Curated demo price dataset",
                                      "Recycler directory (demo data)", "Configured impact assumptions")
ZERO = {"points": 0, "kg": 0.0, "items": 0, "co2e": 0.0, "value": 0}


def _f(label, value, source):
    return {"label": label, "value": str(value), "source": source}


def build_context(c, user: dict, snap: Snapshot) -> dict:
    uid = user["id"]
    t30, tall = totals(snap, since_window()).get(uid, ZERO), totals(snap).get(uid, ZERO)
    cats: dict = {}
    for i in snap.impacts:
        if i["user_id"] == uid:
            cats[i["category"]] = cats.get(i["category"], 0) + i["quantity"]
    waiting = [{"id": s["id"], "label": s["item"]["label"], "quantity": s["item"]["quantity"], "kg": s["estimate"]["impact"]["weight_kg"],
                "points": s["estimate"]["points"]["total"], "item_type": s["item"]["item_type"]} for s in snap.submissions if s["user_id"] == uid and s["status"] == "confirmed"]
    bid, oid = user.get("building_id"), user.get("org_id")
    bscore = reloop_score(c, "building", bid, snap) if bid else None
    lat, lng = user_location(c, user)
    return {"t30": t30, "all": tall, "cats": cats, "waiting": waiting, "building": bscore, "building_gap": gap_analysis(c, "building", bid, snap) if bid else None,
            "building_name": (snap.building(bid) or {}).get("name"), "org_name": (snap.org(oid) or {}).get("name"),
            "org": reloop_score(c, "org", oid, snap) if oid else None, "org_gap": gap_analysis(c, "org", oid, snap) if oid else None,
            "near": nearby(c, lat, lng, service="recycle"), "rank": rank_of(c, uid, "month", snap), "streak": streak_weeks(dates_by_user(snap).get(uid, [])),
            "challenges": [x for x in chl.list_challenges(c, user) if x["is_active"]]}


def _top_cat(cats: dict) -> str | None:
    return category_label(max(cats, key=cats.get)) if cats else None


def _item_from(msg: str, ctx: dict) -> tuple[str | None, int]:
    t = detect_item_type(msg)
    if t:
        return t, 1
    if ctx["waiting"]:
        w = ctx["waiting"][-1]
        return w["item_type"], w["quantity"]
    return None, 1


def i_my_impact(c, user, msg, ctx):
    t, top = ctx["t30"], _top_cat(ctx["cats"])
    facts = [_f("Items verified (last 30 days)", t["items"], S_REC), _f("Weight diverted (last 30 days)", f"{round(t['kg'], 1)} kg", S_REC),
             _f("Points earned (last 30 days)", t["points"], S_REC), _f("Weekly streak", f"{ctx['streak']} weeks", S_REC),
             _f("CO₂e avoided (estimate)", f"{round(t['co2e'], 1)} kg", S_CFG)]
    if ctx["rank"]:
        facts.append(_f("Rank (last 30 days)", f"#{ctx['rank']}", S_REC))
    text = f"You've diverted {round(t['kg'], 1)} kg across {t['items']} items in the last 30 days." if t["items"] else "You haven't had a verified item in the last 30 days yet."
    if top:
        text += f" {top} is your largest category."
    if ctx["waiting"]:
        w = ctx["waiting"]
        text += f" You also have {sum(x['quantity'] for x in w)} item(s) waiting — scheduling a pickup this week would add about {sum(x['points'] for x in w)} points."
        acts = [{"label": "Schedule a pickup", "route": "/pickup"}]
    else:
        text += " Scanning one more item this week keeps your streak going."
        acts = [{"label": "Scan an item", "route": "/scan"}]
    return {"facts": facts, "text": text, "actions": acts}


def i_what_to_do(c, user, msg, ctx):
    it, qty = _item_from(msg, ctx)
    if not it:
        return {"facts": [], "text": "Tell me the item (for example “old laptop” or “power bank”), or scan it and I'll work out what to do with it.", "actions": [{"label": "Scan an item", "route": "/scan"}]}
    info = item_info(it)
    cond = "damaged" if re.search(r"broken|damaged|cracked|dead|not working", msg.lower()) else "good"
    price = c.prices.estimate(it, cond, None, qty)
    act = recommend_action(it, cond, price)
    pts = compute_points(it, qty, None, verified=True)["total"]
    imp = compute_impact(it, qty, None)
    facts = [_f("Estimated recycling value", f"₹{price['recycle']['min']:,} to ₹{price['recycle']['max']:,}", S_CAT)]
    if price["resale"]:
        facts.append(_f("Estimated resale range", f"₹{price['resale']['min']:,} to ₹{price['resale']['max']:,}", S_CAT))
    facts += [_f("Points once verified", pts, S_CFG), _f("Weight and CO₂e (estimate)", f"{imp['weight_kg']} kg, about {imp['co2e_kg']} kg CO₂e", S_CFG)]
    text = f"For {'a' if qty == 1 else str(qty)} {info['label'].lower()}{'' if qty == 1 else 's'} ({'damaged' if cond == 'damaged' else 'assuming it works'}): {act['headline'].lower()}. {act['reason']}"
    return {"facts": facts, "text": text, "actions": [{"label": "Find a recycler", "route": "/recyclers"}, {"label": "Scan it for a real estimate", "route": "/scan"}]}


def i_value(c, user, msg, ctx):
    if ctx["waiting"] and not detect_item_type(msg):
        lo = hi = 0
        facts = []
        for w in ctx["waiting"]:
            s = next((x for x in c.store.list(K.SUBMISSIONS, owner=user["id"]) if x["id"] == w["id"]), None)
            if s:
                v = s["estimate"]["value"]
                rng = v["resale"] if (v["resale"] and s["estimate"]["action"]["primary"] != "recycle") else v["recycle"]
                lo, hi = lo + rng["min"], hi + rng["max"]
                facts.append(_f(w["label"], f"₹{rng['min']:,} to ₹{rng['max']:,}", S_CAT))
        return {"facts": facts + [_f("Total estimated range", f"₹{lo:,} to ₹{hi:,}", S_CAT)],
                "text": f"Your waiting items are worth an estimated ₹{lo:,} to ₹{hi:,} in total. That's a curated demo range, not an offer — scanning or correcting an item sharpens it.",
                "actions": [{"label": "See ReLoop Exchange", "route": "/exchange"}]}
    return i_what_to_do(c, user, msg, ctx)


def i_where(c, user, msg, ctx):
    it = detect_item_type(msg) or (ctx["waiting"][-1]["item_type"] if ctx["waiting"] else None)
    lat, lng = user_location(c, user)
    rows = nearby(c, lat, lng, category=category_of(it) if it else None, service="recycle")[:3]
    if not rows:
        return {"facts": [], "text": "I couldn't find a recycler in the directory that accepts that nearby.", "actions": [{"label": "Browse recyclers", "route": "/recyclers"}]}
    facts = [_f(r["name"], f"{r['distance_km']} km, {'pickup available' if r['pickup_available'] else 'drop-off only'}, {r['processing_days']} days to process", S_DIR) for r in rows]
    what = item_info(it)["label"].lower() if it else "e-waste"
    best = rows[0]
    return {"facts": facts, "text": f"For {what}, the closest option is {best['name']} at {best['distance_km']} km. The directory is demo data — check that a recycler is genuinely authorised before real use.",
            "actions": [{"label": "Open Find a Recycler", "route": "/recyclers"}]}


def i_pickup(c, user, msg, ctx):
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg", msg.lower())
    kg = float(m.group(1)) if m else sum(w["kg"] for w in ctx["waiting"])
    rows = ctx["near"]
    pick = next((r for r in rows if r["pickup_available"] and r["min_pickup_kg"] <= kg), None)
    drop = rows[0] if rows else None
    facts = [_f("Weight considered", f"{kg:g} kg", S_REC if not m else "Your message")]
    if pick:
        facts += [_f(f"{pick['name']} minimum pickup", f"{pick['min_pickup_kg']:g} kg", S_DIR), _f("Distance", f"{pick['distance_km']} km", S_DIR)]
        text = f"Yes — {kg:g} kg clears {pick['name']}'s {pick['min_pickup_kg']:g} kg pickup minimum, so a pickup saves you the trip."
        acts = [{"label": "Schedule a pickup", "route": "/pickup"}]
    else:
        text = f"{kg:g} kg is below the pickup minimum of nearby recyclers, so a drop-off is the better call."
        if drop:
            facts.append(_f("Nearest drop-off", f"{drop['name']}, {drop['distance_km']} km", S_DIR))
        acts = [{"label": "Find a recycler", "route": "/recyclers"}]
    return {"facts": facts, "text": text, "actions": acts}


def _improve(c, user, msg, ctx, scope):
    score = ctx["building"] if scope == "building" else ctx["org"]
    gap = ctx["building_gap"] if scope == "building" else ctx["org_gap"]
    name = ctx["building_name"] if scope == "building" else ctx["org_name"]
    if not score:
        return {"facts": [], "text": "Join a building or campus to see its ReLoop Score and what would improve it.", "actions": []}
    lost = sorted(score["components"], key=lambda x: x["weight"] * (1 - x["value"]), reverse=True)
    worst = lost[0]
    room = round(worst["weight"] * (1 - worst["value"]), 1)
    facts = [_f(f"{name} ReLoop Score", f"{score['score']} of 100", S_BLD), _f(f"Biggest gap: {worst['label']}", f"{room} points available — {worst['detail']}", S_BLD)]
    text = f"{name}'s ReLoop Score is {score['score']}. The most room to grow is {worst['label'].lower()} ({room} points available)."
    acts = [{"label": "Open the dashboard", "route": "/org"}]
    if gap and gap["top_gap"] and gap["drive"]:
        g, d = gap["top_gap"], gap["drive"]
        facts.append(_f(f"{g['label']} share collected", f"{g['actual_share']:.0%} vs {g['expected_share']:.0%} expected (configured assumption)", S_CFG))
        text += f" {g['label']} are currently the largest uncollected category. A collection drive could target the gap: an estimated {d['est_items']} items and {d['est_kg']} kg."
    return {"facts": facts, "text": text, "actions": acts}


def i_building(c, user, msg, ctx):
    return _improve(c, user, msg, ctx, "building")


def i_org(c, user, msg, ctx):
    return _improve(c, user, msg, ctx, "org")


def i_focus(c, user, msg, ctx):
    gap = ctx["org_gap"] if re.search(r"college|campus|our ", msg.lower()) and ctx["org_gap"] else (ctx["building_gap"] or ctx["org_gap"])
    if not gap or not gap["top_gap"]:
        return {"facts": [], "text": "Collection looks balanced against the expected mix right now — keep scanning whatever you have.", "actions": [{"label": "Scan an item", "route": "/scan"}]}
    g = gap["top_gap"]
    facts = [_f(f"{r['label']} collected vs expected", f"{r['actual_share']:.0%} vs {r['expected_share']:.0%}", S_CFG) for r in gap["categories"][:3]]
    return {"facts": facts, "text": f"Focus on {g['label'].lower()} next: only {g['actual_share']:.0%} of collected items, against {g['expected_share']:.0%} expected. " +
            (f"A drive could add roughly {gap['drive']['est_items']} items (estimate)." if gap["drive"] else ""), "actions": [{"label": "Open the dashboard", "route": "/org"}]}


def i_summary(c, user, msg, ctx):
    return {"facts": [], "text": "I can work out what to do with an item, where to take it, what it's worth, whether a pickup makes sense, and how your building or campus can improve. Try one of the quick prompts.",
            "actions": [{"label": "Scan an item", "route": "/scan"}]}


INTENTS = [
    ("pickup_decision", r"\d+(\.\d+)?\s*kg|schedule a pickup|should i (schedule|book)", i_pickup),
    ("college_plan", r"(college|campus|organi[sz]ation|our college).*(increase|collection|improve|plan|do)|what should our", i_org),
    ("building_improve", r"(building|apartment|society|hostel|score).*(improve|increase|better|raise|grow)|improve.*(building|score)", i_building),
    ("focus_category", r"next month|which category|focus|recycle next|what should i recycle", i_focus),
    ("my_impact", r"how much.*(divert|recycl|collect)|my impact|this month|have i diverted|my progress", i_my_impact),
    ("where_recycle", r"where.*(recycle|drop|take|dispose)|recycler|drop.?off|near me", i_where),
    ("value", r"worth|value|price|sell|how much is", i_value),
    ("what_to_do", r"what (should|do) i do|what to do|do with (this|my|the|an|a)|dispose|get rid", i_what_to_do),
]

SYSTEM = (
    "You are ReLoop Advisor, an assistant inside an e-waste recycling app. Answer ONLY from the VERIFIED_FACTS and CONTEXT provided. "
    "Never invent numbers, recyclers or prices; values from the curated dataset are estimates, not offers. Keep it under 90 words, plain text, "
    "and end with one concrete action the user can take in the app. Do not claim any recycler is officially authorised."
)


def answer(c, user: dict, message: str, history: list[dict] | None = None) -> dict:
    c.limiter.check(f"advisor:{user['id']}", 30, 60)
    snap = Snapshot(c)
    ctx = build_context(c, user, snap)
    low = message.lower()
    intent, res = "summary", None
    for name, pat, fn in INTENTS:
        if re.search(pat, low):
            intent, res = name, fn(c, user, message, ctx)
            break
    if res is None:
        res = i_summary(c, user, message, ctx)
    text, generated_by = res["text"], "rules"
    if c.ai.supports_chat:
        try:
            facts_txt = "\n".join(f"- {f['label']}: {f['value']} (source: {f['source']})" for f in res["facts"]) or "- (none)"
            nba = next_best_action(c, user, snap, ctx["building"])
            convo = [{"role": h["role"], "content": str(h["content"])[:400]} for h in (history or [])[-6:] if h.get("role") in ("user", "assistant") and h.get("content")]
            if not convo or convo[-1]["role"] != "user" or convo[-1]["content"] != message[:400]:
                convo.append({"role": "user", "content": message})
            while convo and convo[0]["role"] != "user":
                convo.pop(0)
            sys_prompt = f"{SYSTEM}\n\nVERIFIED_FACTS:\n{facts_txt}\n\nDRAFT_RECOMMENDATION (rules): {res['text']}\nNEXT_BEST_ACTION: {json.dumps(nba.get('title'))}"
            text, generated_by = c.ai.chat(sys_prompt, convo)[:700], "bedrock"
        except AIUnavailable as e:
            log_event("advisor_llm_unavailable", error=str(e)[:160])
    log_event("advisor_chat", user_id=user["id"], intent=intent, generated_by=generated_by)
    return {"intent": intent, "verified": res["facts"], "recommendation": {"text": text, "generated_by": generated_by, "label": "AI-generated recommendation"},
            "actions": res["actions"], "disclaimer": "Verified data comes from your ReLoop records and configured datasets. The recommendation is generated from that data; prices and impact are estimates."}
