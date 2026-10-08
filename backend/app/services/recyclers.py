from __future__ import annotations

import math

from ..models import kinds as K
from .catalog import category_label, recyclers_seed


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def seed_recyclers(c) -> None:
    for r in recyclers_seed():
        c.store.put(K.RECYCLERS, r["id"], {**r, "demo": True})


def decorate(r: dict, lat: float, lng: float) -> dict:
    return {
        **r,
        "distance_km": round(haversine_km(lat, lng, r["lat"], r["lng"]), 1),
        "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={r['lat']},{r['lng']}",
        "accepts_labels": [category_label(a) for a in r["accepts"]],
        "data_label": "Demo data" if r.get("demo") else "Imported data",
    }


def nearby(c, lat: float, lng: float, category: str | None = None, pickup: bool | None = None, q: str | None = None,
           service: str | None = None) -> list[dict]:
    rows = []
    for r in c.store.list(K.RECYCLERS):
        if category and category not in r["accepts"]:
            continue
        if pickup and not r["pickup_available"]:
            continue
        if service and service not in r.get("services", ["recycle"]):
            continue
        if q and q.lower() not in f"{r['name']} {r['address']}".lower():
            continue
        rows.append(decorate(r, lat, lng))
    rows.sort(key=lambda r: r["distance_km"])
    return rows


def user_location(c, user: dict) -> tuple[float, float]:
    b = c.store.get(K.BUILDINGS, user.get("building_id")) if user.get("building_id") else None
    return (b["lat"], b["lng"]) if b else (21.1702, 72.8311)
