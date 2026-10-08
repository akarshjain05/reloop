"""Pickup / drop-off lifecycle. Verification is the moment points, impact, challenges and scores change."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from ..core.errors import AppError, bad_request, conflict, forbidden, not_found
from ..core.logging import log_event
from ..models import kinds as K
from ..repositories.base import new_id, now_iso, parse_ts
from . import challenges, fraud
from .audit import audit
from .catalog import category_of, scoring_cfg
from .impact import compute_impact
from .leaderboard import rank_of
from .orgscore import reloop_score
from .points import compute_points, tier_for
from .recyclers import nearby, user_location
from .stats import Snapshot, totals

SLOTS = ["09:00-11:00", "11:00-13:00", "14:00-16:00", "16:00-18:00"]
LABELS = {"requested": "Requested", "scheduled": "Scheduled", "collector_assigned": "Collector assigned", "picked_up": "Picked up",
          "verified": "Verified", "recycled": "Recycled", "cancelled": "Cancelled"}
TRANSITIONS = {
    "pickup": {"requested": ["scheduled", "cancelled"], "scheduled": ["collector_assigned", "cancelled"], "collector_assigned": ["picked_up"],
               "picked_up": ["verified"], "verified": ["recycled"]},
    "dropoff": {"requested": ["verified", "cancelled"], "verified": ["recycled"]},
}
STATUS_ROLES = {"scheduled": {"ADMIN", "COLLECTOR"}, "collector_assigned": {"ADMIN", "COLLECTOR"}, "picked_up": {"ADMIN", "COLLECTOR"},
                "verified": {"ADMIN", "COLLECTOR"}, "recycled": {"ADMIN"}, "cancelled": {"USER", "ADMIN", "ORGANIZATION_ADMIN"}}
NOTIFY = {"scheduled": ("Pickup confirmed", "Your pickup slot is confirmed."), "collector_assigned": ("Collector assigned", "A collector is on the way for your items."),
          "picked_up": ("Items picked up", "Your items were collected and are heading for verification."), "recycled": ("Items recycled", "Your items completed the recycling process."),
          "cancelled": ("Request cancelled", "Your request was cancelled. Your items are available to schedule again.")}


def can_transition(mode: str, cur: str, nxt: str) -> bool:
    return nxt in TRANSITIONS.get(mode, {}).get(cur, [])


def next_for(p: dict, actor: dict) -> list[str]:
    out = []
    for nxt in TRANSITIONS[p["mode"]].get(p["status"], []):
        if actor["role"] in STATUS_ROLES[nxt] and (nxt != "cancelled" or p["user_id"] == actor["id"] or actor["role"] == "ADMIN"):
            out.append(nxt)
    return out


def view(p: dict, actor: dict) -> dict:
    return {**p, "status_label": LABELS[p["status"]], "next_statuses": [{"status": s, "label": LABELS[s]} for s in next_for(p, actor)],
            "steps": [{"status": s, "label": LABELS[s]} for s in (["requested", "scheduled", "collector_assigned", "picked_up", "verified", "recycled"] if p["mode"] == "pickup" else ["requested", "verified", "recycled"])]}


def create_pickup(c, user: dict, data: dict) -> dict:
    subs = []
    for sid in data["submission_ids"]:
        s = c.store.get(K.SUBMISSIONS, sid)
        if not s or s["user_id"] != user["id"]:
            raise not_found("Item")
        if s["status"] != "confirmed":
            raise conflict("Only confirmed items that aren't already scheduled can be added.", "item_not_available")
        subs.append(s)
    cats = {category_of(s["item"]["item_type"]) for s in subs}
    total_kg = sum(s["estimate"]["impact"]["weight_kg"] for s in subs)
    mode = data.get("mode", "pickup")
    lat, lng = user_location(c, user)

    def accepts_all(r):
        return cats <= set(r["accepts"])

    if mode == "pickup":
        if not data.get("address") or not data.get("date") or not data.get("slot"):
            raise bad_request("Choose an address, a date and a time slot for the pickup.", "missing_schedule")
        if data["slot"] not in SLOTS:
            raise bad_request("That time slot isn't available.", "bad_slot")
        day = datetime.strptime(data["date"], "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()
        if not (today <= day <= today + timedelta(days=30)):
            raise bad_request("Pick a date within the next 30 days.", "bad_date")
    cands = [r for r in nearby(c, lat, lng, service="recycle") if accepts_all(r) and (mode == "dropoff" or (r["pickup_available"] and r["min_pickup_kg"] <= total_kg))]
    rec = None
    if data.get("recycler_id"):
        rec = next((r for r in cands if r["id"] == data["recycler_id"]), None)
        if not rec:
            raise bad_request("That recycler can't take this pickup (categories, pickup service or minimum weight).", "recycler_mismatch")
    else:
        rec = cands[0] if cands else None
    if not rec:
        raise conflict("No recycler nearby can take this combination for pickup. Try a drop-off, or split the items.", "no_recycler")
    now = now_iso()
    p = {"id": new_id("pck"), "user_id": user["id"], "user_name": user["name"], "building_id": user.get("building_id"), "org_id": user.get("org_id"), "mode": mode,
         "submission_ids": [s["id"] for s in subs], "items": [{"submission_id": s["id"], "label": s["item"]["label"], "quantity": s["item"]["quantity"]} for s in subs],
         "recycler_id": rec["id"], "recycler_name": rec["name"], "address": data.get("address"), "date": data.get("date"), "slot": data.get("slot"),
         "status": "requested", "history": [{"status": "requested", "at": now, "by": user["name"]}], "total_kg": round(total_kg, 2),
         "estimated_points": sum(s["estimate"]["points"]["total"] for s in subs), "collector_id": None, "collector_name": None,
         "drop_code": secrets.token_hex(3).upper() if mode == "dropoff" else None, "created_at": now, "rewards": None}
    c.store.put(K.PICKUPS, p["id"], p)
    for s in subs:
        s.update(status="pickup_requested", pickup_id=p["id"])
        c.store.put(K.SUBMISSIONS, s["id"], s)
    c.notifier.notify(user["id"], "pickup_requested", "Request received" if mode == "pickup" else "Drop-off planned",
                      f"{rec['name']} will handle {len(subs)} item(s)." if mode == "pickup" else f"Show code {p['drop_code']} at {rec['name']}.")
    log_event("pickup_created", user_id=user["id"], mode=mode, items=len(subs), kg=round(total_kg, 2), recycler=rec["id"])
    return view(p, user)


def list_pickups(c, user: dict, status: str | None = None) -> list[dict]:
    rows = c.store.list(K.PICKUPS) if user["role"] in ("ADMIN", "COLLECTOR") else c.store.list(K.PICKUPS, owner=user["id"])
    if status:
        rows = [p for p in rows if p["status"] == status]
    rows.sort(key=lambda p: p["created_at"], reverse=True)
    return [view(p, user) for p in rows[:100]]


def get_pickup(c, user: dict, pid: str) -> dict:
    p = c.store.get(K.PICKUPS, pid)
    if not p:
        raise not_found("Pickup")
    if p["user_id"] != user["id"] and user["role"] not in ("ADMIN", "COLLECTOR", "ORGANIZATION_ADMIN"):
        raise forbidden()
    return view(p, user)


def transition(c, actor: dict, pid: str, status: str, verified_weight_kg: float | None = None, verified_match: bool = True,
               note: str | None = None, collector_id: str | None = None) -> dict:
    p = c.store.get(K.PICKUPS, pid)
    if not p:
        raise not_found("Pickup")
    if actor["role"] not in STATUS_ROLES[status]:
        raise forbidden("Your role can't make this change.")
    if status == "cancelled" and p["user_id"] != actor["id"] and actor["role"] != "ADMIN":
        raise forbidden()
    if not can_transition(p["mode"], p["status"], status):
        raise conflict(f"A request that is '{LABELS[p['status']]}' can't move to '{LABELS[status]}'.", "invalid_transition")
    if status == "collector_assigned":
        cid = collector_id or (actor["id"] if actor["role"] == "COLLECTOR" else None)
        col = c.store.get(K.USERS, cid) if cid else next((u for u in c.store.list(K.USERS) if u["role"] == "COLLECTOR"), None)
        if not col:
            raise bad_request("No collector available to assign.", "no_collector")
        p.update(collector_id=col["id"], collector_name=col["name"])
    if status in ("picked_up", "verified") and p["mode"] == "pickup" and actor["role"] == "COLLECTOR" and p.get("collector_id") not in (None, actor["id"]):
        raise forbidden("This pickup is assigned to another collector.")

    p["status"] = status
    p["history"].append({"status": status, "at": now_iso(), "by": actor.get("name"), **({"note": note} if note else {})})
    rewards = None
    if status == "verified":
        rewards = _award(c, actor, p, verified_weight_kg, verified_match)
        p["rewards"] = rewards
    elif status == "recycled":
        for imp in [i for i in c.store.list(K.IMPACT, owner=p["user_id"]) if i.get("pickup_id") == p["id"]]:
            imp["status"] = "recycled"
            c.store.put(K.IMPACT, imp["id"], imp)
        for sid in p["submission_ids"]:
            s = c.store.get(K.SUBMISSIONS, sid)
            if s:
                s["status"] = "recycled"
                c.store.put(K.SUBMISSIONS, sid, s)
    elif status == "cancelled":
        for sid in p["submission_ids"]:
            s = c.store.get(K.SUBMISSIONS, sid)
            if s and s["status"] == "pickup_requested":
                s["status"] = "confirmed"
                s.pop("pickup_id", None)
                c.store.put(K.SUBMISSIONS, sid, s)
    c.store.put(K.PICKUPS, p["id"], p)
    if status in NOTIFY:
        c.notifier.notify(p["user_id"], f"pickup_{status}", *NOTIFY[status])
    audit(c, actor, f"pickup.{status}", p["id"], note=note)
    log_event("pickup_status", pickup_id=p["id"], status=status, actor_role=actor["role"])
    return view(p, actor)


def _award(c, actor: dict, p: dict, verified_weight_kg: float | None, verified_match: bool) -> dict:
    snap = Snapshot(c)
    user = snap.user(p["user_id"])
    subs = [s for s in (c.store.get(K.SUBMISSIONS, sid) for sid in p["submission_ids"]) if s]
    rank_before = rank_of(c, user["id"], "month", snap)
    points_before = totals(snap).get(user["id"], {}).get("points", 0)
    score_before = reloop_score(c, "building", user["building_id"], snap)["score"] if user.get("building_id") else None
    est_total = sum(s["estimate"]["impact"]["weight_kg"] for s in subs) or 1.0
    today = datetime.now(timezone.utc).date()
    cap = scoring_cfg()["points"]["max_daily_points"]
    used = sum(r["points"] for r in snap.ledger if r["user_id"] == user["id"] and r["status"] == "posted" and r.get("ref_type") == "submission"
               and parse_ts(r["created_at"]).date() == today)
    awards, events, tot_pts, tot_kg, tot_co2, tot_items, held_any = [], [], 0, 0.0, 0.0, 0, False
    for s in subs:
        item, qty = s["item"], s["item"]["quantity"]
        est_w = s["estimate"]["impact"]["weight_kg"]
        w_total = round(verified_weight_kg * est_w / est_total, 3) if verified_weight_kg else est_w
        per_item = w_total / qty
        imp = compute_impact(item["item_type"], qty, per_item, verified=True)
        doc = {"id": new_id("imp"), "user_id": user["id"], "building_id": user.get("building_id"), "org_id": user.get("org_id"), "submission_id": s["id"],
               "pickup_id": p["id"], "created_at": now_iso(), "status": "verified", "item_type": imp["item_type"], "category": imp["category"], "quantity": qty,
               "weight_kg": imp["weight_kg"], "co2e_kg": imp["co2e_kg"], "materials_kg": imp["materials_kg"], "value_mid_inr": s["estimate"]["value"]["recycle_mid"],
               "weight_source": "collector_weighed" if verified_weight_kg else "estimated"}
        c.store.put(K.IMPACT, doc["id"], doc)
        bonus_n = challenges.active_bonus_count(c, user["id"], imp["item_type"], imp["category"])
        pts = compute_points(item["item_type"], qty, per_item, verified=True, segregation_ok=verified_match, active_challenges=bonus_n)
        held = bool(fraud.open_flags_for(c, s["id"])) or s["fraud"]["status"] == "pending_review"
        award, capped = pts["total"], False
        if not held:
            room = max(0, cap - used)
            if award > room:
                award, capped = room, True
            used += award
        row = {"id": new_id("pts"), "user_id": user["id"], "points": award, "status": "held" if held else "posted",
               "reason": f"{item['label']} recycled through a verified {'pickup' if p['mode'] == 'pickup' else 'drop-off'}", "ref_type": "submission", "ref_id": s["id"],
               "created_at": now_iso(), "meta": {"breakdown": pts["breakdown"], "capped": capped, "uncapped_total": pts["total"], "pickup_id": p["id"], "formula_version": pts["formula_version"]}}
        c.store.put(K.LEDGER, row["id"], row)
        s.update(status="verified", verified_at=now_iso(), awarded_points=award, points_status=row["status"], impact_id=doc["id"])
        c.store.put(K.SUBMISSIONS, s["id"], s)
        if not verified_match:
            c.store.put(K.FRAUD, new_id("flg"), {"id": new_id("flg"), "submission_id": s["id"], "user_id": user["id"], "user_name": user["name"], "score": 40,
                                                   "reasons": ["MISMATCH"], "details": ["Verifier reported the item did not match what was declared."], "status": "open",
                                                   "created_at": now_iso(), "message": "Verifier reported a mismatch."})
        if not held:
            events += challenges.apply_progress(c, user, doc)
        held_any = held_any or held
        tot_pts += 0 if held else award
        tot_kg += imp["weight_kg"]
        tot_co2 += imp["co2e_kg"]
        tot_items += qty
        awards.append({"submission_id": s["id"], "label": item["label"], "points": award, "status": row["status"], "capped": capped, "breakdown": pts["breakdown"]})
    snap2 = Snapshot(c)
    rank_after = rank_of(c, user["id"], "month", snap2)
    tier_before, tier_after = tier_for(points_before), tier_for(totals(snap2).get(user["id"], {}).get("points", 0))
    score_after = reloop_score(c, "building", user["building_id"], snap2)["score"] if user.get("building_id") else None
    c.notifier.notify(user["id"], "item_verified", "Your items were verified", f"{tot_items} item(s), {round(tot_kg, 1)} kg diverted from landfill.")
    if tot_pts:
        c.notifier.notify(user["id"], "points_earned", f"+{tot_pts} ReLoop points earned", "Verified recycling action.")
    if held_any:
        c.notifier.notify(user["id"], "points_held", "Some points are pending review", "We're double-checking a flagged submission before releasing them.")
    if rank_before and rank_after and rank_after < rank_before:
        c.notifier.notify(user["id"], "rank_up", f"You moved up {rank_before - rank_after} place(s)", f"You're now #{rank_after} in the last 30 days.")
    return {"points": tot_pts, "kg": round(tot_kg, 2), "co2e_kg": round(tot_co2, 2), "items": tot_items, "awards": awards, "points_held": held_any,
            "rank_before": rank_before, "rank_after": rank_after, "tier_before": tier_before["name"], "tier_after": tier_after["name"], "points_to_next_tier": tier_after["points_to_next"], "next_tier": tier_after["next_name"], "building_score_before": score_before, "building_score_after": score_after,
            "challenge_events": events, "disclaimer": "CO₂e is an illustrative estimate based on configured impact factors."}


def fast_forward(c, user: dict, pid: str) -> dict:
    """DEMO ONLY: walks a request through the collector/admin steps so a solo demo can show the reward moment."""
    if not c.settings.demo_mode:
        raise forbidden("Demo shortcuts are disabled.")
    p = c.store.get(K.PICKUPS, pid)
    if not p:
        raise not_found("Pickup")
    if p["user_id"] != user["id"] and user["role"] != "ADMIN":
        raise forbidden()
    sys_actor = {"id": "system_demo", "name": "Demo fast-forward", "role": "ADMIN"}
    path = ["scheduled", "collector_assigned", "picked_up", "verified"] if p["mode"] == "pickup" else ["verified"]
    out = view(p, user)
    for step in path:
        cur = c.store.get(K.PICKUPS, pid)
        if can_transition(cur["mode"], cur["status"], step):
            out = transition(c, sys_actor, pid, step)
    return view(c.store.get(K.PICKUPS, pid), user)
