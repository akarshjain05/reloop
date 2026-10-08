"""Community challenges. Progress only moves on VERIFIED recycling actions by participants."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core.errors import conflict, not_found
from ..models import kinds as K
from ..repositories.base import new_id, now_iso, parse_ts


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_active(ch: dict) -> bool:
    return ch["status"] == "active" and parse_ts(ch["starts_at"]) <= _now() <= parse_ts(ch["ends_at"])


def visible_to(ch: dict, user: dict) -> bool:
    return ch.get("scope") == "global" or ch.get("org_id") == user.get("org_id")


def _view(ch: dict, part: dict | None) -> dict:
    goal = ch["goal"] or 1
    days_left = max(0, (parse_ts(ch["ends_at"]) - _now()).days)
    return {**ch, "pct": min(100, int(100 * ch["progress"] / goal)), "joined": part is not None,
            "my_contribution": (part or {}).get("contribution", 0), "days_left": days_left, "is_active": is_active(ch),
            "unit": "kg" if ch["metric"] == "kg" else "items"}


def list_challenges(c, user: dict) -> list[dict]:
    parts = {p["challenge_id"]: p for p in c.store.list(K.PARTICIPANTS, owner=user["id"])}
    rows = [_view(ch, parts.get(ch["id"])) for ch in c.store.list(K.CHALLENGES) if visible_to(ch, user)]
    rows.sort(key=lambda r: (not r["is_active"], -r["pct"]))
    return rows


def join(c, user: dict, challenge_id: str) -> dict:
    ch = c.store.get(K.CHALLENGES, challenge_id)
    if not ch or not visible_to(ch, user):
        raise not_found("Challenge")
    if not is_active(ch):
        raise conflict("This challenge isn't open right now.", "challenge_closed")
    pid = f"{challenge_id}:{user['id']}"
    part = c.store.get(K.PARTICIPANTS, pid)
    if not part:
        part = {"id": pid, "challenge_id": challenge_id, "user_id": user["id"], "joined_at": now_iso(), "contribution": 0.0}
        c.store.put(K.PARTICIPANTS, pid, part)
        ch["participants"] = ch.get("participants", 0) + 1
        c.store.put(K.CHALLENGES, challenge_id, ch)
        c.notifier.notify(user["id"], "challenge_joined", f"You joined {ch['title']}", "Verified recycling now counts towards this goal.")
    return _view(ch, part)


def joined_active(c, user_id: str) -> list[dict]:
    out = []
    for p in c.store.list(K.PARTICIPANTS, owner=user_id):
        ch = c.store.get(K.CHALLENGES, p["challenge_id"])
        if ch and is_active(ch):
            out.append(ch)
    return out


def matches(ch: dict, impact: dict) -> bool:
    if ch.get("item_type"):
        return impact["item_type"] == ch["item_type"]
    if ch.get("category"):
        return impact["category"] == ch["category"]
    return True


def active_bonus_count(c, user_id: str, item_type: str, category: str) -> int:
    probe = {"item_type": item_type, "category": category}
    return sum(1 for ch in joined_active(c, user_id) if matches(ch, probe))


def apply_progress(c, user: dict, impact: dict) -> list[dict]:
    """Returns the milestone events that fired (for the reward screen)."""
    events = []
    for ch in joined_active(c, user["id"]):
        if not matches(ch, impact):
            continue
        inc = impact["weight_kg"] if ch["metric"] == "kg" else impact["quantity"]
        before = int(100 * ch["progress"] / ch["goal"])
        ch["progress"] = round(ch["progress"] + inc, 2)
        after = int(100 * ch["progress"] / ch["goal"])
        pid = f"{ch['id']}:{user['id']}"
        part = c.store.get(K.PARTICIPANTS, pid)
        part["contribution"] = round(part["contribution"] + inc, 2)
        c.store.put(K.PARTICIPANTS, pid, part)
        for mark in (50, 75, 100):
            if before < mark <= after:
                events.append({"challenge": ch["title"], "milestone": mark})
                c.notifier.notify(user["id"], "challenge_milestone", f"{ch['title']} reached {mark}%",
                                  f"{ch['progress']:g} of {ch['goal']:g} {'kg' if ch['metric'] == 'kg' else 'items'} so far.")
        if ch["progress"] >= ch["goal"] and ch["status"] == "active":
            ch["status"] = "completed"
            ch["completed_at"] = now_iso()
            _reward_participants(c, ch)
        c.store.put(K.CHALLENGES, ch["id"], ch)
    return events


def _reward_participants(c, ch: dict) -> None:
    contributors = [p for p in c.store.list(K.PARTICIPANTS) if p["challenge_id"] == ch["id"] and p["contribution"] > 0]
    if not contributors or not ch.get("reward_points"):
        return
    share = min(250, ch["reward_points"] // len(contributors))
    for p in contributors:
        rid = new_id("pts")
        c.store.put(K.LEDGER, rid, {"id": rid, "user_id": p["user_id"], "points": share, "status": "posted",
                                    "reason": f"Challenge completed: {ch['title']}", "ref_type": "challenge", "ref_id": ch["id"],
                                    "created_at": now_iso(), "meta": {"community_reward": ch["reward_points"]}})
        c.notifier.notify(p["user_id"], "challenge_completed", f"{ch['title']} complete!", f"+{share} community points added to your balance.")


def create(c, actor: dict, data: dict) -> dict:
    now = _now()
    ch = {"id": new_id("chl"), "title": data["title"], "description": data.get("description", ""), "metric": data["metric"],
          "goal": float(data["goal"]), "progress": 0.0, "reward_points": data.get("reward_points", 0), "item_type": data.get("item_type"),
          "category": data.get("category"), "scope": data.get("scope", "org"), "org_id": actor.get("org_id"), "status": "active",
          "starts_at": now.isoformat(timespec="seconds"), "ends_at": (now + timedelta(days=data.get("days", 14))).isoformat(timespec="seconds"),
          "participants": 0, "created_by": actor["id"], "demo": False}
    c.store.put(K.CHALLENGES, ch["id"], ch)
    return ch
