from __future__ import annotations

from .stats import Snapshot, totals


def analytics(c, snap: Snapshot | None = None) -> dict:
    snap = snap or Snapshot(c)
    subs, preds = snap.submissions, snap.predictions
    confirmed = [p for p in preds if p.get("confirmed")]
    corrected = sum(1 for p in confirmed if p.get("corrected"))
    n = len(confirmed) or 1
    users = [u for u in snap.users if u["role"] == "USER"]
    t = totals(snap)
    active = [u for u in users if t.get(u["id"], {}).get("items", 0) > 0]
    per_user: dict = {}
    for s in subs:
        if s["status"] in ("verified", "recycled"):
            per_user[s["user_id"]] = per_user.get(s["user_id"], 0) + 1
    pk = [p for p in snap.pickups if p["status"] != "cancelled"]
    done = [p for p in pk if p["status"] in ("verified", "recycled")]
    chl = snap.challenges
    actions: dict = {}
    for s in subs:
        if s.get("action_choice"):
            actions[s["action_choice"]] = actions.get(s["action_choice"], 0) + 1
    resale_potential = sum(s["estimate"]["value"].get("resale_mid", 0) for s in subs if s["status"] in ("confirmed", "analyzed"))
    return {
        "total_submissions": len(subs), "verified_submissions": sum(1 for s in subs if s["status"] in ("verified", "recycled")),
        "kg_diverted": round(sum(i["weight_kg"] for i in snap.impacts), 1), "co2e_kg_avoided": round(sum(i["co2e_kg"] for i in snap.impacts), 1),
        "recycling_value_inr": int(sum(i.get("value_mid_inr", 0) for i in snap.impacts)), "open_resale_potential_inr": int(resale_potential),
        "participation_rate": round(len(active) / len(users), 3) if users else 0, "repeat_users": sum(1 for v in per_user.values() if v >= 2),
        "pickup_completion_rate": round(len(done) / len(pk), 3) if pk else 0, "challenge_completion_rate": round(sum(1 for c_ in chl if c_["status"] == "completed") / len(chl), 3) if chl else 0,
        "ai_accuracy": {"n": len(confirmed), "correct_first_attempt_pct": round(100 * (len(confirmed) - corrected) / n), "corrected_pct": round(100 * corrected / n)},
        "action_choices": actions, "open_fraud_flags": sum(1 for f in snap.fraud if f["status"] == "open"),
        "data_note": "Seeded demo data plus live activity. Figures are estimates based on configured assumptions.",
    }
