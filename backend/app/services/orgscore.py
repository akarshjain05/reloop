"""ReLoop Score (0-100) for a building or organisation, shown WITH its calculation, plus gap analysis."""
from __future__ import annotations

from ..models import kinds as K
from ..repositories.base import parse_ts
from .catalog import category_label, impact_cfg, scoring_cfg
from .stats import Snapshot, monthly_series, since_window, totals

COMMITTED = ("confirmed", "pickup_requested", "collected", "verified", "recycled")
VERIFIED = ("verified", "recycled")


def _scope(snap: Snapshot, scope: str, scope_id: str) -> tuple[list[dict], set[str]]:
    blds = [b for b in snap.buildings if (b["id"] == scope_id if scope == "building" else b["org_id"] == scope_id)]
    return blds, {b["id"] for b in blds}


def reloop_score(c, scope: str, scope_id: str, snap: Snapshot | None = None) -> dict:
    snap = snap or Snapshot(c)
    cfg = scoring_cfg()["reloop_score"]
    since = since_window(cfg["window_days"])
    blds, bids = _scope(snap, scope, scope_id)
    members = sum(b["members"] for b in blds)

    imp = [i for i in snap.impacts if i.get("building_id") in bids and parse_ts(i["created_at"]) >= since]
    active = {i["user_id"] for i in imp}
    part_rate = len(active) / members if members else 0.0
    participation = min(1.0, part_rate / cfg["participation_target"])

    subs = [s for s in snap.submissions if s.get("building_id") in bids and parse_ts(s["created_at"]) >= since and s["status"] in COMMITTED]
    committed = sum(s["item"]["quantity"] for s in subs)
    verified = sum(s["item"]["quantity"] for s in subs if s["status"] in VERIFIED)
    verified_disposal = (verified / committed) if committed else 0.0

    kg = sum(i["weight_kg"] for i in imp)
    target_kg = members * cfg["target_kg_per_member_month"]
    diversion = min(1.0, kg / target_kg) if target_kg else 0.0

    scans = [b for b in snap.bin_scans if b.get("building_id") in bids and b.get("confirmed") and parse_ts(b["created_at"]) >= since]
    segregation = (sum(b["clean_ratio"] for b in scans) / len(scans)) if scans else cfg["default_segregation"]

    weeks_active = 0
    for k in range(4):
        lo, hi = since_window(7 * (k + 1)), since_window(7 * k)
        if any(lo <= parse_ts(i["created_at"]) < hi for i in snap.impacts if i.get("building_id") in bids):
            weeks_active += 1
    consistency = weeks_active / 4

    w = cfg["weights"]
    comps = [
        ("participation", "Participation", participation, f"{len(active)} of {members} members active ({part_rate:.0%}); full marks at {cfg['participation_target']:.0%}"),
        ("verified_disposal", "Verified disposal", verified_disposal, f"{verified} of {committed} committed items verified"),
        ("diversion", "Waste diverted", diversion, f"{kg:.1f} kg of a {target_kg:.0f} kg monthly target"),
        ("segregation", "Segregation quality", segregation, f"{len(scans)} confirmed bin checks" if scans else "No bin checks yet — using a neutral default"),
        ("consistency", "Consistency", consistency, f"{weeks_active} of the last 4 weeks had verified activity"),
    ]
    components = [{"key": k, "label": label, "weight": w[k], "value": round(v, 3), "points": round(w[k] * v, 1), "detail": d} for k, label, v, d in comps]
    score = round(sum(x["points"] for x in components), 1)
    return {
        "score": score, "components": components, "window_days": cfg["window_days"],
        "formula": "ReLoop Score = 30 x participation + 25 x verified disposal + 20 x waste diverted + 15 x segregation quality + 10 x consistency (each 0 to 1)",
        "kpis": {"members": members, "active_users": len(active), "participation_rate": round(part_rate, 3), "recycling_rate": round(verified_disposal, 3),
                 "kg_30d": round(kg, 1), "items_30d": sum(i["quantity"] for i in imp), "co2e_kg_30d": round(sum(i["co2e_kg"] for i in imp), 1), "target_kg": round(target_kg, 1)},
    }


def gap_analysis(c, scope: str, scope_id: str, snap: Snapshot | None = None) -> dict:
    snap = snap or Snapshot(c)
    cfg = impact_cfg()
    blds, bids = _scope(snap, scope, scope_id)
    since = since_window(90)
    imp = [i for i in snap.impacts if i.get("building_id") in bids and parse_ts(i["created_at"]) >= since]
    total_items = sum(i["quantity"] for i in imp) or 1
    actual: dict[str, int] = {}
    for i in imp:
        actual[i["category"]] = actual.get(i["category"], 0) + i["quantity"]
    rows = []
    for cat, exp in cfg["expected_item_mix"].items():
        share = actual.get(cat, 0) / total_items
        rows.append({"category": cat, "label": category_label(cat), "expected_share": exp, "actual_share": round(share, 3), "gap": round(exp - share, 3), "items": actual.get(cat, 0)})
    rows.sort(key=lambda r: -r["gap"])
    top = rows[0] if rows and rows[0]["gap"] > 0.03 else None
    drive = None
    if top:
        members = sum(b["members"] for b in blds)
        d = cfg["drive"]
        est_items = round(members * d["participation_rate"] * d["items_per_participant"])
        kinds = [f for f in cfg["impact_factors"].values() if f["category"] == top["category"]]
        avg_w = sum(f["average_weight_kg"] for f in kinds) / max(1, len(kinds))
        avg_co2 = sum(f["co2e_kg_per_item"] for f in kinds) / max(1, len(kinds))
        drive = {"category": top["category"], "label": top["label"], "est_items": est_items, "est_kg": round(est_items * avg_w, 1),
                 "est_co2e_kg": round(est_items * avg_co2, 1), "basis": "Estimate from configured drive assumptions (participation and items per participant)."}
    return {"categories": rows, "top_gap": top, "drive": drive, "window_days": 90, "basis": "Collected share vs an expected item mix (configured assumption, not measured)."}


def org_summary(c, scope: str, scope_id: str, snap: Snapshot | None = None) -> dict:
    snap = snap or Snapshot(c)
    blds, bids = _scope(snap, scope, scope_id)
    users = [u for u in snap.users if u["role"] == "USER" and u.get("building_id") in bids]
    score = reloop_score(c, scope, scope_id, snap)
    imp_all = [i for i in snap.impacts if i.get("building_id") in bids]
    ledger_all = [row for row in snap.ledger if snap.user(row["user_id"]) and (snap.user(row["user_id"]) or {}).get("building_id") in bids]
    tt = totals(snap, since_window())
    contributors = sorted(({"id": u["id"], "name": u["name"], "points": tt.get(u["id"], {}).get("points", 0), "kg": round(tt.get(u["id"], {}).get("kg", 0.0), 1),
                            "items": tt.get(u["id"], {}).get("items", 0)} for u in users), key=lambda r: (-r["points"], r["name"]))[:8]
    cats: dict[str, dict] = {}
    for i in imp_all:
        if parse_ts(i["created_at"]) >= since_window(90):
            d = cats.setdefault(i["category"], {"category": i["category"], "label": category_label(i["category"]), "items": 0, "kg": 0.0})
            d["items"] += i["quantity"]
            d["kg"] = round(d["kg"] + i["weight_kg"], 1)
    top_buildings = []
    if scope == "org":
        for b in blds:
            s = reloop_score(c, "building", b["id"], snap)
            top_buildings.append({"id": b["id"], "name": b["name"], "score": s["score"], "kg_30d": s["kpis"]["kg_30d"], "participation_rate": s["kpis"]["participation_rate"]})
        top_buildings.sort(key=lambda r: -r["score"])
    entity = snap.building(scope_id) if scope == "building" else snap.org(scope_id)
    campaigns = [ch for ch in snap.challenges if ch["status"] in ("active", "completed") and (ch.get("scope") == "global" or ch.get("org_id") in {b["org_id"] for b in blds})]
    return {
        "scope": scope, "id": scope_id, "name": entity["name"] if entity else scope_id, "score": score,
        "all_time": {"kg": round(sum(i["weight_kg"] for i in imp_all), 1), "items": sum(i["quantity"] for i in imp_all), "co2e_kg": round(sum(i["co2e_kg"] for i in imp_all), 1)},
        "trend": monthly_series(imp_all, ledger_all, 6),
        "top_categories": sorted(cats.values(), key=lambda r: -r["items"])[:6],
        "top_contributors": contributors, "top_buildings": top_buildings,
        "gap": gap_analysis(c, scope, scope_id, snap),
        "campaigns": [{"id": ch["id"], "title": ch["title"], "progress": ch["progress"], "goal": ch["goal"], "metric": ch["metric"], "status": ch["status"],
                       "pct": min(100, int(100 * ch["progress"] / ch["goal"]))} for ch in campaigns][:5],
    }
