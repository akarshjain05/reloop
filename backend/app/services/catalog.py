"""Loads the configured assumptions and the curated demo datasets (all editable files under app/data)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

DATA = Path(__file__).resolve().parent.parent / "data"

CONDITIONS = ("like_new", "good", "fair", "damaged")
CONDITION_LABELS = {"like_new": "Like new", "good": "Used — good", "fair": "Used — fair", "damaged": "Damaged"}
ACTIONS = ("resell", "repair", "recycle", "donate")

_ITEM_ALIASES = {
    "phone": "smartphone", "mobile": "smartphone", "cellphone": "smartphone", "pc": "desktop_pc",
    "computer": "desktop_pc", "desktop": "desktop_pc", "tv": "television", "headphones": "earphones",
    "earbuds": "earphones", "hdd": "hard_drive", "ssd": "hard_drive", "adapter": "charger",
    "modem": "router", "notebook": "laptop", "powerbank": "power_bank", "screen": "monitor",
}
_CONDITION_ALIASES = {
    "new": "like_new", "used": "good", "working": "good", "ok": "good", "old": "fair", "worn": "fair",
    "broken": "damaged", "dead": "damaged", "cracked": "damaged", "faulty": "damaged", "not_working": "damaged",
}


@lru_cache
def impact_cfg() -> dict:
    return yaml.safe_load((DATA / "assumptions" / "impact_factors.yaml").read_text())


@lru_cache
def scoring_cfg() -> dict:
    return yaml.safe_load((DATA / "assumptions" / "scoring.yaml").read_text())


@lru_cache
def price_cfg() -> dict:
    return json.loads((DATA / "demo" / "price_catalog.json").read_text())


@lru_cache
def recyclers_seed() -> list[dict]:
    return json.loads((DATA / "demo" / "recyclers.json").read_text())["recyclers"]


def factors() -> dict:
    return impact_cfg()["impact_factors"]


def item_types() -> list[str]:
    return list(factors())


def _slug(v: str | None) -> str:
    return (v or "").strip().lower().replace(" ", "_").replace("-", "_")


def normalize_item_type(t: str | None) -> str:
    s = _slug(t)
    if s in factors():
        return s
    return _ITEM_ALIASES.get(s, "other_electronics")


def normalize_condition(c: str | None) -> str:
    s = _slug(c) or "good"
    if s in CONDITIONS:
        return s
    return _CONDITION_ALIASES.get(s, "good")


def item_info(t: str | None) -> dict:
    return factors()[normalize_item_type(t)]


def category_label(key: str) -> str:
    return impact_cfg()["categories"].get(key, key)


def category_of(item_type: str | None) -> str:
    return item_info(item_type)["category"]


TYPE_PATTERNS = [
    (r"power[\s_\-]?bank", "power_bank"), (r"hard[\s_\-]?drive|\bhdd\b|\bssd\b", "hard_drive"),
    (r"mother[\s_\-]?board|\bpcb\b", "motherboard"), (r"ear[\s_\-]?(phone|bud)|headphone|headset", "earphones"),
    (r"laptop|macbook|notebook|thinkpad", "laptop"), (r"smart[\s_\-]?phone|iphone|phone|mobile|galaxy", "smartphone"),
    (r"tablet|ipad", "tablet"), (r"desktop|\bcpu\b|\btower\b", "desktop_pc"), (r"monitor|screen|display", "monitor"),
    (r"\btv\b|television", "television"), (r"printer", "printer"), (r"keyboard", "keyboard"), (r"mouse", "mouse"),
    (r"charger|adapter|adaptor", "charger"), (r"cable|wire|cord", "cable"), (r"router|modem", "router"), (r"battery", "battery"),
]


def detect_item_type(text: str | None) -> str | None:
    low = (text or "").lower()
    return next((t for pat, t in TYPE_PATTERNS if re.search(pat, low)), None)
