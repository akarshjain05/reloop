"""Price estimation behind a provider interface. The default provider reads a curated DEMO dataset;
a live marketplace / refurbisher API can be plugged in by implementing PriceProvider."""
from __future__ import annotations

from typing import Protocol

from .catalog import normalize_condition, normalize_item_type, price_cfg


class PriceProvider(Protocol):
    def estimate(self, item_type: str, condition: str = "good", brand: str | None = None, quantity: int = 1) -> dict: ...


def _round(v: float) -> int:
    if v >= 10000:
        return int(round(v / 500) * 500)
    if v >= 1000:
        return int(round(v / 100) * 100)
    if v >= 100:
        return int(round(v / 10) * 10)
    return int(round(v))


class CuratedPriceProvider:
    def estimate(self, item_type, condition="good", brand=None, quantity=1) -> dict:
        cfg = price_cfg()
        meta = cfg["meta"]
        key = normalize_item_type(item_type)
        cond = normalize_condition(condition)
        qty = max(1, int(quantity))
        base = cfg["types"].get(key) or cfg["types"]["other_electronics"]
        bf = cfg["brand_factors"].get((brand or "generic").strip().lower(), 1.0)
        cf = cfg["condition_factors"][cond]

        resale = None
        if cf > 0 and base["resale"][1] > 0:
            resale = {"min": _round(base["resale"][0] * cf * bf * qty), "max": _round(base["resale"][1] * cf * bf * qty)}
        recycle = {"min": _round(base["recycle"][0] * qty), "max": _round(base["recycle"][1] * qty)}
        resale_mid = round((resale["min"] + resale["max"]) / 2) if resale else 0
        recycle_mid = round((recycle["min"] + recycle["max"]) / 2)
        return {
            "currency": meta["currency"],
            "label": meta["label"],
            "resale": resale,
            "recycle": recycle,
            "resale_mid": resale_mid,
            "recycle_mid": recycle_mid,
            "mid_value": resale_mid or recycle_mid,
            "source": meta["source"],
            "source_updated": meta["updated"],
            "is_live": meta["is_live"],
            "disclaimer": meta["disclaimer"],
            "inputs": {"item_type": key, "condition": cond, "brand": brand, "quantity": qty},
        }
