"""ReLoop points — transparent, documented formula (see data/assumptions/scoring.yaml)."""
from __future__ import annotations

from .catalog import item_info, normalize_item_type, scoring_cfg


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_points(
    item_type: str,
    quantity: int = 1,
    weight_kg_per_item: float | None = None,
    verified: bool = False,
    segregation_ok: bool = True,
    active_challenges: int = 0,
) -> dict:
    cfg = scoring_cfg()["points"]
    key = normalize_item_type(item_type)
    info = item_info(key)
    avg = info["average_weight_kg"]
    w = float(weight_kg_per_item) if weight_kg_per_item else avg
    qty = max(1, int(quantity))

    wf = cfg["weight_factor"]
    weight_factor = _clamp(wf["floor"] + wf["slope"] * (w / avg), wf["floor"], wf["cap"])
    recovery_factor = cfg["recovery_factor"]["base"] + info["recovery_score"] / cfg["recovery_factor"]["divisor"]
    subtotal = info["base_points"] * weight_factor * recovery_factor * qty

    verified_bonus = subtotal * cfg["verified_bonus_pct"] if verified else 0.0
    segregation = subtotal * cfg["segregation_bonus_pct"] if (verified and segregation_ok) else 0.0
    event_pct = min(cfg["event_bonus_cap_pct"], cfg["event_bonus_pct_per_challenge"] * max(0, active_challenges))
    event_bonus = subtotal * event_pct

    total = round(subtotal + verified_bonus + segregation + event_bonus)
    breakdown = [
        {"label": f"Base for {info['label'].lower()} × weight × recovery", "points": round(subtotal, 1),
         "detail": f"{info['base_points']} × {weight_factor:.2f} × {recovery_factor:.2f} × {qty}"},
    ]
    if verified:
        breakdown.append({"label": "Verified pickup / drop-off bonus", "points": round(verified_bonus, 1), "detail": f"+{int(cfg['verified_bonus_pct'] * 100)}%"})
        breakdown.append({"label": "Correct segregation bonus", "points": round(segregation, 1), "detail": f"+{int(cfg['segregation_bonus_pct'] * 100)}%, item matched what was declared" if segregation else "Item did not match what was declared"})
    if event_bonus:
        breakdown.append({"label": "Community challenge bonus", "points": round(event_bonus, 1), "detail": f"+{int(event_pct * 100)}%"})
    return {"total": total, "verified": verified, "breakdown": breakdown, "formula_version": scoring_cfg()["version"]}


def tier_for(points: int) -> dict:
    tiers = scoring_cfg()["tiers"]
    current = tiers[0]
    for t in tiers:
        if points >= t["min"]:
            current = t
    nxt = next((t for t in tiers if t["min"] > current["min"]), None)
    span = (nxt["min"] - current["min"]) if nxt else 1
    return {
        "name": current["name"],
        "next_name": nxt["name"] if nxt else None,
        "points_to_next": (nxt["min"] - points) if nxt else 0,
        "progress_pct": 100 if not nxt else int(100 * (points - current["min"]) / span),
    }
