"""Transparent environmental-impact estimator. All numbers come from data/assumptions/impact_factors.yaml."""
from __future__ import annotations

from .catalog import impact_cfg, item_info, normalize_item_type


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_impact(item_type: str, quantity: int = 1, weight_kg_per_item: float | None = None, verified: bool = False) -> dict:
    cfg = impact_cfg()
    key = normalize_item_type(item_type)
    info = item_info(key)
    avg = info["average_weight_kg"]
    w = float(weight_kg_per_item) if weight_kg_per_item else avg
    qty = max(1, int(quantity))
    ratio = _clamp(w / avg, 0.3, 3.0)
    weight_total = round(w * qty, 3)
    recovery = info["recovery_score"]
    return {
        "item_type": key,
        "category": info["category"],
        "quantity": qty,
        "weight_kg": weight_total,
        "co2e_kg": round(info["co2e_kg_per_item"] * qty * ratio, 2),
        "recovery_score": recovery,
        "materials_kg": {m: round(weight_total * share * recovery / 100, 3) for m, share in info["materials"].items() if share > 0},
        "diverted_kg": weight_total if verified else 0.0,
        "assumptions_version": cfg["version"],
        "is_estimate": True,
        "disclaimer": cfg["disclaimer"],
    }
