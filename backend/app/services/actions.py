"""Explainable resell / repair / recycle / donate rules. Every recommendation carries its reason."""
from __future__ import annotations

from .catalog import item_info, normalize_condition

RESELL_THRESHOLD_INR = 1500


def recommend_action(item_type: str, condition: str, price: dict) -> dict:
    info = item_info(item_type)
    cond = normalize_condition(condition)
    resale = price.get("resale")
    resale_max = resale["max"] if resale else 0

    if info["hazardous"]:
        primary, fallback = "recycle", None
        headline = "Recycle at an authorised drop-off"
        reason = "Lithium batteries and power banks can start fires in bins and trucks — hand them to an authorised e-waste recycler, never resell or bin them."
    elif cond == "damaged":
        primary, fallback = "recycle", None
        headline = "Recycle through an authorised recycler"
        reason = "Damaged electronics can't be resold safely. Recycling recovers metals and keeps hazardous parts out of landfill."
    elif cond in ("like_new", "good"):
        if resale_max >= RESELL_THRESHOLD_INR:
            primary, fallback = "resell", "recycle"
            headline = "Resell if it works — recycle if it doesn't"
            reason = f"Working and possibly worth up to ₹{resale_max:,} on resale. Reuse avoids more impact than recycling."
        else:
            primary, fallback = "donate", "recycle"
            headline = "Donate if it works — recycle if it doesn't"
            reason = "Resale value is low, so donating keeps a working item in use."
    else:  # fair
        if info["repairable"]:
            primary, fallback = "repair", "recycle"
            headline = "Repair or resell if it works — recycle if beyond repair"
            reason = "A small repair can restore most of its value. If repair isn't worth it, recycle."
        else:
            primary, fallback = "donate", "recycle"
            headline = "Donate if it works — recycle if it doesn't"
            reason = "Low resale value; donating keeps a working item in use."
    return {"primary": primary, "fallback": fallback, "headline": headline, "reason": reason, "rule_based": True}
