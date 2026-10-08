"""Read helpers shared by dashboards, leaderboards and the advisor."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ..models import kinds as K
from ..repositories.base import days_ago, parse_ts

WINDOW_DAYS = 30


class Snapshot:
    """Request-scoped read cache: one API call reads each table at most once."""

    def __init__(self, c) -> None:
        self.c = c
        self._d: dict[str, list[dict]] = {}

    def _g(self, kind: str) -> list[dict]:
        if kind not in self._d:
            self._d[kind] = self.c.store.list(kind)
        return self._d[kind]

    users = property(lambda s: s._g(K.USERS))
    buildings = property(lambda s: s._g(K.BUILDINGS))
    orgs = property(lambda s: s._g(K.ORGS))
    impacts = property(lambda s: s._g(K.IMPACT))
    ledger = property(lambda s: s._g(K.LEDGER))
    submissions = property(lambda s: s._g(K.SUBMISSIONS))
    predictions = property(lambda s: s._g(K.PREDICTIONS))
    pickups = property(lambda s: s._g(K.PICKUPS))
    challenges = property(lambda s: s._g(K.CHALLENGES))
    participants = property(lambda s: s._g(K.PARTICIPANTS))
    bin_scans = property(lambda s: s._g(K.BIN_SCANS))
    fraud = property(lambda s: s._g(K.FRAUD))

    def user(self, uid: str) -> dict | None:
        return next((u for u in self.users if u["id"] == uid), None)

    def building(self, bid: str | None) -> dict | None:
        return next((b for b in self.buildings if b["id"] == bid), None)

    def org(self, oid: str | None) -> dict | None:
        return next((o for o in self.orgs if o["id"] == oid), None)


def since_window(days: int = WINDOW_DAYS) -> datetime:
    return days_ago(days)


def _zero() -> dict:
    return {"points": 0, "kg": 0.0, "items": 0, "co2e": 0.0, "value": 0, "last_at": None}


def totals(snap: Snapshot, since: datetime | None = None) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(_zero)
    for row in snap.ledger:
        if row.get("status") != "posted" or (since and parse_ts(row["created_at"]) < since):
            continue
        out[row["user_id"]]["points"] += row["points"]
    for i in snap.impacts:
        at = parse_ts(i["created_at"])
        if since and at < since:
            continue
        t = out[i["user_id"]]
        t["kg"] += i["weight_kg"]
        t["items"] += i["quantity"]
        t["co2e"] += i["co2e_kg"]
        t["value"] += i.get("value_mid_inr", 0)
        t["last_at"] = max(t["last_at"], at) if t["last_at"] else at
    return out


def streak_weeks(dates: list[datetime]) -> int:
    """Consecutive ISO weeks with at least one verified action, ending this week (or last week as grace)."""
    weeks = {d.isocalendar()[:2] for d in dates}
    d = datetime.now(timezone.utc)
    if d.isocalendar()[:2] not in weeks:
        d -= timedelta(days=7)
    n = 0
    while d.isocalendar()[:2] in weeks:
        n += 1
        d -= timedelta(days=7)
    return n


def dates_by_user(snap: Snapshot) -> dict[str, list[datetime]]:
    out: dict[str, list[datetime]] = defaultdict(list)
    for i in snap.impacts:
        out[i["user_id"]].append(parse_ts(i["created_at"]))
    return out


def weekly_activity(dates: list[datetime], weeks: int = 12) -> list[dict]:
    """Oldest -> newest flags for the streak strip."""
    now = datetime.now(timezone.utc)
    have = {d.isocalendar()[:2] for d in dates}
    out = []
    for k in range(weeks - 1, -1, -1):
        d = now - timedelta(days=7 * k)
        out.append({"week": f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}", "active": d.isocalendar()[:2] in have})
    return out


def monthly_series(impacts: list[dict], ledger: list[dict] | None = None, months: int = 6) -> list[dict]:
    """Calendar-month buckets, oldest first, always `months` long (zeros included)."""
    now = datetime.now(timezone.utc)
    keys = []
    y, m = now.year, now.month
    for _ in range(months):
        keys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    keys.reverse()
    buckets = {k: {"month": f"{k[0]}-{k[1]:02d}", "kg": 0.0, "items": 0, "co2e": 0.0, "points": 0, "participants": set()} for k in keys}
    for i in impacts:
        at = parse_ts(i["created_at"])
        b = buckets.get((at.year, at.month))
        if b:
            b["kg"] += i["weight_kg"]
            b["items"] += i["quantity"]
            b["co2e"] += i["co2e_kg"]
            b["participants"].add(i["user_id"])
    for row in ledger or []:
        if row.get("status") != "posted":
            continue
        at = parse_ts(row["created_at"])
        b = buckets.get((at.year, at.month))
        if b:
            b["points"] += row["points"]
    return [{**b, "kg": round(b["kg"], 1), "co2e": round(b["co2e"], 1), "participants": len(b["participants"])} for b in buckets.values()]
