from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..ai.agent import strands_available
from ..core.errors import not_found
from ..models import kinds as K
from ..services.stats import Snapshot
from .deps import current_user, get_c

router = APIRouter(tags=["system"])
VERSION = "1.0.0"


@router.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@router.get("/system/status")
def status(c=Depends(get_c)):
    s = c.settings
    runtime = {
        "ai": c.ai.name, "model_id": c.ai.model_id, "bedrock_region": s.bedrock_region if c.ai.name == "bedrock" else None,
        "agent": "strands" if (s.use_strands and c.ai.name == "bedrock" and strands_available()) else "pipeline",
        "store": c.store.name, "table": s.dynamodb_table or None, "storage": c.storage.kind, "bucket": s.s3_bucket or None,
        "auth": c.auth.kind, "region": s.aws_region, "in_lambda": s.in_lambda,
    }
    on_aws = runtime["ai"] == "bedrock" or runtime["store"] == "dynamodb" or runtime["storage"] == "s3" or runtime["auth"] == "cognito"
    banner = ("Demo mode: no AWS calls are being made. Deploy the SAM stack to see Bedrock, DynamoDB, S3 and Cognito in action."
              if not on_aws else "Running on AWS services: " + ", ".join(n for n, v in (("Bedrock", runtime["ai"] == "bedrock"), ("DynamoDB", runtime["store"] == "dynamodb"),
                                                                                       ("S3", runtime["storage"] == "s3"), ("Cognito", runtime["auth"] == "cognito")) if v) + ".")
    return {"app": "ReLoop", "version": VERSION, "demo_mode": s.demo_mode, "runtime": runtime, "on_aws": on_aws, "banner": banner,
            "locale": {"currency": s.currency, "symbol": s.currency_symbol, "unit": s.weight_unit, "country": s.country, "locale": s.locale},
            "demo_accounts": [{"email": e, "role": r, "password": s.demo_password} for e, r in
                              (("demo@reloop.app", "USER"), ("org@reloop.app", "ORGANIZATION_ADMIN"), ("collector@reloop.app", "COLLECTOR"), ("admin@reloop.app", "ADMIN"))] if s.demo_mode else []}


@router.get("/public/stats")
def public_stats(c=Depends(get_c)):
    snap = Snapshot(c)
    users = {u["id"] for u in snap.users if u["role"] == "USER"}
    return {"items": sum(i["quantity"] for i in snap.impacts), "kg": round(sum(i["weight_kg"] for i in snap.impacts), 1),
            "co2e_kg": round(sum(i["co2e_kg"] for i in snap.impacts), 1), "active_users": len({i["user_id"] for i in snap.impacts} & users),
            "buildings": len(snap.buildings), "is_demo": True,
            "note": "Seeded demo numbers plus live activity from this deployment. CO₂e is an illustrative estimate."}


@router.get("/public/buildings")
def public_buildings(c=Depends(get_c)):
    return [{"id": b["id"], "name": b["name"], "neighborhood": b["neighborhood"]} for b in c.store.list(K.BUILDINGS)]


@router.get("/media/{key:path}")
def media(key: str, c=Depends(get_c)):
    if c.storage.kind != "local":
        raise not_found("Image")
    p = c.storage.path(key)
    if not p.is_file():
        raise not_found("Image")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/notifications")
def notifications(user=Depends(current_user), c=Depends(get_c)):
    rows = sorted(c.store.list(K.NOTIFS, owner=user["id"]), key=lambda n: n["created_at"], reverse=True)[:30]
    return {"unread": sum(1 for n in rows if not n["read"]), "items": rows}


@router.post("/notifications/read")
def mark_read(user=Depends(current_user), c=Depends(get_c)):
    for n in c.store.list(K.NOTIFS, owner=user["id"]):
        if not n["read"]:
            n["read"] = True
            c.store.put(K.NOTIFS, n["id"], n)
    return {"ok": True}
