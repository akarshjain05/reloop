"""Leaderboards are computed views over the points ledger + verified impact (no stored ranks to drift)."""
from __future__ import annotations

from ..models import kinds as K
from .points import tier_for
from .stats import Snapshot, dates_by_user, since_window, streak_weeks, totals


def _rows(snap: Snapshot, users: list[dict], period: str) -> list[dict]:
    since = since_window() if period == "month" else None
    tt = totals(snap, since)
    dates = dates_by_user(snap)
    rows = []
    for u in users:
        t = tt.get(u["id"]) or {"points": 0, "kg": 0.0, "items": 0}
        rows.append({"id": u["id"], "name": u["name"], "points": t["points"], "kg": round(t["kg"], 1), "items": t["items"],
                     "streak": streak_weeks(dates.get(u["id"], []))})
    rows.sort(key=lambda r: (-r["points"], -r["kg"], r["name"]))
    for n, r in enumerate(rows, 1):
        r["rank"] = n
    return rows


def _me_block(rows: list[dict], me_id: str, all_time_points: int, period_label: str, unit: str = "you") -> dict:
    mine = next((r for r in rows if r["id"] == me_id), None)
    tier = tier_for(all_time_points)
    if not mine or mine["points"] <= 0:
        msg = "Your first verified item puts you on the board."
    else:
        msg = f"You're #{mine['rank']} {period_label}."
    if tier["next_name"]:
        msg += f" {tier['points_to_next']} more points to reach {tier['next_name']}."
    return {"rank": mine["rank"] if mine else None, "points": mine["points"] if mine else 0, "message": msg, "tier": tier}


def leaderboard(c, user: dict, scope: str, period: str = "month", snap: Snapshot | None = None) -> dict:
    snap = snap or Snapshot(c)
    users = [u for u in snap.users if u["role"] == "USER"]
    label = "in the last 30 days" if period == "month" else "of all time"
    all_time = totals(snap).get(user["id"], {}).get("points", 0)

    if scope == "neighborhood":
        mine_b = snap.building(user.get("building_id"))
        hood = mine_b["neighborhood"] if mine_b else None
        blds = [b for b in snap.buildings if b["neighborhood"] == hood]
        since = since_window() if period == "month" else None
        tt = totals(snap, since)
        rows = []
        for b in blds:
            members = [u for u in users if u.get("building_id") == b["id"]]
            org = snap.org(b["org_id"])
            rows.append({"id": b["id"], "name": b["name"], "org": org["name"] if org else "", "points": sum(tt.get(u["id"], {}).get("points", 0) for u in members),
                         "kg": round(sum(tt.get(u["id"], {}).get("kg", 0.0) for u in members), 1),
                         "items": sum(tt.get(u["id"], {}).get("items", 0) for u in members), "streak": None,
                         "participants": sum(1 for u in members if tt.get(u["id"], {}).get("items", 0) > 0)})
        rows.sort(key=lambda r: (-r["points"], -r["kg"], r["name"]))
        for n, r in enumerate(rows, 1):
            r["rank"], r["is_me"] = n, r["id"] == user.get("building_id")
        mine = next((r for r in rows if r["is_me"]), None)
        msg = f"Your building is #{mine['rank']} in {hood} {label}." if mine else "Join a building to appear here."
        return {"scope": scope, "period": period, "title": f"Top buildings in {hood}" if hood else "Top buildings", "unit": "building",
                "entries": rows[:15], "me": {"rank": mine["rank"] if mine else None, "points": mine["points"] if mine else 0, "message": msg, "tier": tier_for(all_time)}}

    if scope == "global":
        pool, title = users, "Top contributors across all campuses and societies"
    elif scope == "campus":
        org = snap.org(user.get("org_id"))
        pool, title = [u for u in users if u.get("org_id") == user.get("org_id")], f"Top students at {org['name']}" if org else "Top contributors on your campus"
    elif scope == "building":
        b = snap.building(user.get("building_id"))
        pool, title = [u for u in users if u.get("building_id") == user.get("building_id")], f"Top residents of {b['name']}" if b else "Top residents"
    else:
        raise ValueError("unknown scope")
    rows = _rows(snap, pool, period)
    for r in rows:
        r["is_me"] = r["id"] == user["id"]
    me = _me_block(rows, user["id"], all_time, label)
    top = rows[:15]
    mine_row = next((r for r in rows if r["is_me"]), None)
    if mine_row and mine_row["rank"] > 15:
        top = top + [mine_row]
    return {"scope": scope, "period": period, "title": title, "unit": "person", "entries": top, "me": me, "total_participants": len(rows)}


def rank_of(c, user_id: str, period: str = "month", snap: Snapshot | None = None) -> int | None:
    snap = snap or Snapshot(c)
    rows = _rows(snap, [u for u in snap.users if u["role"] == "USER"], period)
    return next((r["rank"] for r in rows if r["id"] == user_id), None)
