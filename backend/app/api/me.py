from __future__ import annotations

from fastapi import APIRouter, Depends

from ..services.catalog import category_label
from ..services.dashboard import dashboard
from ..services.stats import Snapshot, dates_by_user, monthly_series, since_window, streak_weeks, totals, weekly_activity
from ..repositories.base import parse_ts
from .deps import current_user, get_c

router = APIRouter(tags=["me"])


@router.get("/dashboard")
def get_dashboard(user=Depends(current_user), c=Depends(get_c)):
    return dashboard(c, user)


@router.get("/impact")
def impact(user=Depends(current_user), c=Depends(get_c)):
    snap = Snapshot(c)
    uid = user["id"]
    mine = [i for i in snap.impacts if i["user_id"] == uid]
    ledger = [r for r in snap.ledger if r["user_id"] == uid]
    cats: dict = {}
    mats: dict = {}
    for i in mine:
        d = cats.setdefault(i["category"], {"category": i["category"], "label": category_label(i["category"]), "kg": 0.0, "items": 0, "co2e_kg": 0.0})
        d["kg"] = round(d["kg"] + i["weight_kg"], 2)
        d["items"] += i["quantity"]
        d["co2e_kg"] = round(d["co2e_kg"] + i["co2e_kg"], 2)
        for m, v in i.get("materials_kg", {}).items():
            mats[m] = round(mats.get(m, 0) + v, 3)
    t_all, t_30 = totals(snap).get(uid, {}), totals(snap, since_window()).get(uid, {})
    dates = dates_by_user(snap).get(uid, [])
    recent = [i for i in mine if parse_ts(i["created_at"]) >= since_window()]
    return {
        "monthly": monthly_series(mine, ledger, 6), "categories": sorted(cats.values(), key=lambda r: -r["items"]), "materials_kg": mats,
        "totals": {"all": {k: round(t_all.get(k, 0), 1) for k in ("kg", "items", "co2e", "points")}, "last_30_days": {k: round(t_30.get(k, 0), 1) for k in ("kg", "items", "co2e", "points")}},
        "streak": {"weeks": streak_weeks(dates), "weekly": weekly_activity(dates, 12)},
        "this_month": {"items": sum(i["quantity"] for i in recent), "kg": round(sum(i["weight_kg"] for i in recent), 1), "co2e_kg": round(sum(i["co2e_kg"] for i in recent), 1),
                       "weighed_by_collector": sum(1 for i in recent if i.get("weight_source") == "collector_weighed")},
        "explain": [
            {"label": "kg diverted", "meaning": "Weight of items that went through a verified pickup or drop-off instead of a bin. Collector-weighed when available, otherwise estimated from typical item weight."},
            {"label": "CO₂e avoided", "meaning": "An illustrative estimate from configured impact factors for the items you recycled. It is not a certified carbon figure."},
            {"label": "Materials", "meaning": "Estimated recoverable material (kg) using each item's recovery score and typical composition."},
        ],
        "disclaimer": "Impact figures are estimates based on configured assumptions (see docs/DATA_SOURCES.md).",
    }
