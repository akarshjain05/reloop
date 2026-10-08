"""Deterministic demo provider. NOT computer vision: the result derives from the file name / user hint,
falling back to a hash of the image bytes, so the same image always yields the same answer."""
from __future__ import annotations

import hashlib
import re

from ..services.catalog import detect_item_type, item_info
from .types import AIProvider, BinAnalysis, ItemAnalysis, bin_advice, build_bin_categories

_BRAND_HINTS = [(r"apple|macbook|iphone|ipad", "apple"), (r"dell", "dell"), (r"\bhp\b|hewlett", "hp"), (r"lenovo|thinkpad", "lenovo"),
                (r"samsung|galaxy", "samsung"), (r"asus", "asus"), (r"acer", "acer")]
_FALLBACK_ORDER = ["smartphone", "laptop", "charger", "keyboard", "mouse", "monitor", "router", "earphones",
                   "hard_drive", "power_bank", "tablet", "cable"]


class MockProvider(AIProvider):
    name = "mock"
    model_id = "reloop-mock-v1"

    def analyze_item(self, image, content_type, filename=None, hint=None) -> ItemAnalysis:
        h = hashlib.sha256(image).digest()
        text = f"{filename or ''} {hint or ''}".lower()
        matched = detect_item_type(text)
        item_type = matched or _FALLBACK_ORDER[h[0] % len(_FALLBACK_ORDER)]
        brand = next((b for pat, b in _BRAND_HINTS if re.search(pat, text)), None)
        if re.search(r"damaged|broken|cracked|dead|faulty", text):
            condition = "damaged"
        elif re.search(r"like[\s_\-]?new|\bnew\b", text):
            condition = "like_new"
        elif re.search(r"\bfair\b|\bold\b|worn", text):
            condition = "fair"
        else:
            condition = "good"
        confidence = 0.90 + (h[1] % 6) / 100 if matched else 0.74 + (h[1] % 14) / 100
        return ItemAnalysis(
            item_type=item_type, label=item_info(item_type)["label"], confidence=round(confidence, 2),
            condition=condition, brand=brand, quantity=1,
            notes="Demo AI: deterministic result from the file name / image hash — not computer vision.",
            provider=self.name, model_id=self.model_id, latency_ms=120,
        )

    def analyze_bin(self, image, content_type, filename=None) -> BinAnalysis:
        h = hashlib.sha256(image).digest()
        name = (filename or "").lower()
        if re.search(r"mixed|bin|trash|waste", name):
            present = {k: (True, 0.9, "") for k in ("plastic", "paper", "metal", "organic", "e_waste", "hazardous")}
            present["e_waste"] = (True, 0.84, "Charger cable and a small circuit board visible")
            present["hazardous"] = (True, 0.77, "Loose battery visible")
        else:
            keys = ["plastic", "paper", "metal", "organic", "e_waste", "hazardous"]
            present = {k: (h[i] % 4 != 0, 0.7 + (h[i + 8] % 25) / 100, "") for i, k in enumerate(keys)}
        cats = build_bin_categories(present)
        return BinAnalysis(categories=cats, advice=bin_advice(cats), provider=self.name, model_id=self.model_id, latency_ms=140)
