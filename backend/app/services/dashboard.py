"""User dashboard + 'Your Next Best Action' — every insight must lead to an action."""
from __future__ import annotations

from ..models import kinds as K
from ..repositories.base import parse_ts
from . import challenges as chl
from .catalog import category_label, impact_cfg
from .impact import compute_impact
from .leaderboard import _rows
from .orgscore import gap_analysis, reloop_score
from .points import compute_points, tier_for
from .stats import Snapshot, dates_by_user, since_window, streak_weeks, totals, weekly_activity

ZERO = {"points": 0, "kg": 0.0, "items": 0, "co2e": 0.0, "value": 0}


def _small_batch_estimate(category: str, n: int = 3) -> dict:
    """What a handful of typical items in the gap category would yield (configured assumptions)."""
    key = next((k for k, f in impact_cfg()["impact_factors"].items() if f["category"] == category), "charger")
    pts = compute_points(key, n, None, verified=True)["total"]
    imp = compute_impact(key, n, None, verified=True)
    return {"items": n, "points": pts, "kg": imp["weight_kg"], "co2e_kg": imp["co2e_kg"], "example": key.replace("_", " ")}


def next_best_action(c, user: dict, snap: Snapshot, bscore: dict | None) -> dict:
    waiting = [s for s in snap.submissions if s["user_id"] == user["id"] and s["status"] == "confirmed"]
    if waiting:
        n = sum(s["item"]["quantity"] for s in waiting)
        est = {"points": sum(s["estimate"]["points"]["total"] for s in waiting), "kg": round(sum(s["estimate"]["impact"]["weight_kg"] for s in waiting), 1),
               "co2e_kg": round(sum(s["estimate"]["impact"]["co2e_kg"] for s in waiting), 1)}
        return {"rule": "waiting_items", "title": f"You have {n} old electronic{'s' if n != 1 else ''} waiting for disposal",
                "body": "Drop them at an authorised recycler or schedule a pickup this week to turn them into points and measurable impact.",
                "estimate": est, "estimate_label": "Estimated once verified", "cta": {"label": "Schedule a pickup", "route": "/pickup"}}
    unconfirmed = [s for s in snap.submissions if s["user_id"] == user["id"] and s["status"] == "analyzed"]
    if unconfirmed:
        return {"rule": "confirm_scan", "title": "Confirm the item you just scanned",
                "body": "A quick check of the item and its condition makes the value estimate more accurate.",
                "estimate": None, "cta": {"label": "Review result", "route": f"/scan?resume={unconfirmed[-1]['id']}"}}
    if bscore and user.get("building_id"):
        k = bscore["kpis"]
        below = 1 - (k["kg_30d"] / k["target_kg"]) if k["target_kg"] else 0
        gap = gap_analysis(c, "building", user["building_id"], snap)
        if below >= 0.1 and gap["top_gap"]:
            cat = gap["top_gap"]
            batch = _small_batch_estimate(cat["category"])
            if user["role"] == "ORGANIZATION_ADMIN" and gap["drive"]:
                d = gap["drive"]
                return {"rule": "building_gap_admin", "title": f"Your building is {below:.0%} below its monthly diversion target",
                        "body": f"{cat['label']} are the biggest uncollected category. Organise a {cat['label'].lower()} collection drive this weekend.",
                        "estimate": {"items": d["est_items"], "kg": d["est_kg"], "co2e_kg": d["est_co2e_kg"]}, "estimate_label": "Estimated drive result (configured assumptions)",
                        "cta": {"label": "Plan the drive", "route": "/org"}}
            return {"rule": "building_gap", "title": f"Your building is {below:.0%} below its monthly diversion target",
                    "body": f"{cat['label']} are the biggest uncollected category. Scan the old {batch['example']}s and similar items in your drawer.",
                    "estimate": {"points": batch["points"], "kg": batch["kg"], "co2e_kg": batch["co2e_kg"]}, "estimate_label": f"Estimated for {batch['items']} items once verified",
                    "cta": {"label": "Scan an item", "route": "/scan"}}
    return {"rule": "scan_next", "title": "Scan your next item", "body": "Point your camera at an old device, cable or charger. WasteLens tells you what it is, what it's worth and the best next step.",
            "estimate": None, "cta": {"label": "Scan an item", "route": "/scan"}}


def _recent(snap: Snapshot, uid: str) -> list[dict]:
    rows = []
    for r in snap.ledger:
        if r["user_id"] == uid:
            rows.append({"type": "points", "title": r["reason"], "detail": f"+{r['points']} points" + (" (pending review)" if r["status"] == "held" else ""), "at": r["created_at"]})
    for s in snap.submissions:
        if s["user_id"] == uid and s["status"] in ("analyzed", "confirmed", "pickup_requested"):
            label = {"analyzed": "Scanned, awaiting your confirmation", "confirmed": "Confirmed, ready to schedule", "pickup_requested": "Pickup or drop-off requested"}[s["status"]]
            rows.append({"type": "item", "title": s["item"]["label"], "detail": label, "at": s["created_at"]})
    rows.sort(key=lambda r: r["at"], reverse=True)
    return rows[:8]


def dashboard(c, user: dict) -> dict:
    snap = Snapshot(c)
    uid = user["id"]
    all_t, m_t = totals(snap).get(uid, ZERO), totals(snap, since_window()).get(uid, ZERO)
    held = sum(r["points"] for r in snap.ledger if r["user_id"] == uid and r["status"] == "held")
    rows = _rows(snap, [u for u in snap.users if u["role"] == "USER"], "month")
    mine = next((r for r in rows if r["id"] == uid), None)
    dates = dates_by_user(snap).get(uid, [])
    b = snap.building(user.get("building_id"))
    bscore = reloop_score(c, "building", b["id"], snap) if b else None
    challenge = None
    for ch in chl.list_challenges(c, user):
        if ch["is_active"] and (ch["joined"] or challenge is None):
            challenge = ch
            if ch["joined"]:
                break
    tier = tier_for(all_t["points"])
    co2 = round(m_t["co2e"], 1)
    return {
        "user": {k: user.get(k) for k in ("id", "name", "email", "role")},
        "points": {"total": all_t["points"], "pending_review": held, "tier": tier},
        "month": {"kg": round(m_t["kg"], 1), "items": m_t["items"], "co2e_kg": co2, "value_inr": int(m_t["value"]), "points": m_t["points"], "label": "Last 30 days"},
        "streak": {"weeks": streak_weeks(dates), "weekly": weekly_activity(dates, 12)},
        "rank": {"position": mine["rank"] if mine and m_t["points"] > 0 else None, "of": len(rows),
                 "message": (f"You're #{mine['rank']} in the last 30 days. " if mine and m_t["points"] > 0 else "Your first verified item puts you on the board. ") +
                            (f"{tier['points_to_next']} more points to reach {tier['next_name']}." if tier["next_name"] else "You're at the top tier.")},
        "building": {"id": b["id"], "name": b["name"], "score": bscore["score"], "components": bscore["components"], "kpis": bscore["kpis"]} if b else None,
        "next_best_action": next_best_action(c, user, snap, bscore),
        "challenge": challenge,
        "recent": _recent(snap, uid),
        "impact_story": (f"Your verified recycling actions in the last 30 days diverted {round(m_t['kg'], 1)} kg of e-waste, which prevented an estimated {co2} kg CO₂e associated with disposal."
                         if m_t["items"] else "Once a pickup or drop-off is verified, your impact shows up here."),
        "disclaimer": "CO₂e and value figures are estimates based on configured assumptions and a market dataset.",
    }
