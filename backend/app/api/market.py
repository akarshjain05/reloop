from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.errors import not_found
from ..models import kinds as K
from ..services.actions import recommend_action
from ..services.catalog import CONDITION_LABELS, category_label, item_info, normalize_condition, normalize_item_type, price_cfg
from ..services.recyclers import decorate, nearby, user_location
from .deps import current_user, get_c

router = APIRouter(tags=["market"])


@router.get("/prices/estimate")
def estimate(item_type: str = Query(max_length=40), condition: str = "good", brand: str | None = Query(default=None, max_length=40),
             quantity: int = Query(default=1, ge=1, le=50), user=Depends(current_user), c=Depends(get_c)):
    price = c.prices.estimate(item_type, condition, brand, quantity)
    return {**price, "action": recommend_action(item_type, condition, price)}


@router.get("/prices/catalog")
def catalog(user=Depends(current_user)):
    cfg = price_cfg()
    rows = []
    for m in cfg["models"]:
        info = item_info(m["type"])
        resale = {"min": m["resale"][0], "max": m["resale"][1]} if m.get("resale") else None
        recycle = {"min": m["recycle"][0], "max": m["recycle"][1]}
        action = recommend_action(m["type"], m["condition"], {"resale": resale, "recycle": recycle})
        rows.append({"id": m["id"], "name": m["name"], "type": normalize_item_type(m["type"]), "brand": m["brand"], "condition": normalize_condition(m["condition"]),
                     "condition_label": CONDITION_LABELS[m["condition"]], "category": info["category"], "category_label": category_label(info["category"]),
                     "resale": resale, "recycle": recycle, "action": {k: action[k] for k in ("primary", "fallback", "headline", "reason")}})
    return {"items": rows, "label": cfg["meta"]["label"], "source": cfg["meta"]["source"], "updated": cfg["meta"]["updated"], "is_live": cfg["meta"]["is_live"],
            "disclaimer": cfg["meta"]["disclaimer"], "currency": cfg["meta"]["currency"]}


@router.get("/recyclers")
def recyclers(lat: float | None = Query(default=None, ge=-90, le=90), lng: float | None = Query(default=None, ge=-180, le=180), category: str | None = Query(default=None, max_length=40),
              pickup: bool | None = None, q: str | None = Query(default=None, max_length=60), service: str | None = Query(default=None, max_length=20),
              user=Depends(current_user), c=Depends(get_c)):
    if lat is None or lng is None:
        lat, lng = user_location(c, user)
    rows = nearby(c, lat, lng, category=category, pickup=pickup, q=q, service=service)
    return {"origin": {"lat": lat, "lng": lng}, "items": rows, "data_label": "Demo data",
            "notice": "These are fictional demo entries. None is verified or officially authorised; real CPCB / state board authorisation data can be imported."}


@router.get("/recyclers/{rid}")
def recycler(rid: str, user=Depends(current_user), c=Depends(get_c)):
    r = c.store.get(K.RECYCLERS, rid)
    if not r:
        raise not_found("Recycler")
    lat, lng = user_location(c, user)
    return decorate(r, lat, lng)
