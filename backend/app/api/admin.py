from __future__ import annotations

import csv
import io
import re

from fastapi import APIRouter, Depends, Response

from ..core.errors import bad_request, conflict, not_found
from ..models import kinds as K
from ..models.schemas import AdjustIn, ChallengeIn, RecyclerIn, ResolveIn, VerifyIn
from ..repositories.base import new_id, now_iso
from ..services import challenges as chl
from ..services import pickups
from ..services.analytics import analytics
from ..services.audit import audit
from ..services.catalog import impact_cfg
from ..services.stats import Snapshot, totals
from .deps import get_c, require

router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN = require("ADMIN")
V_LABEL = {"verified": "Verified", "verified_demo": "Verified in the demo dataset (fictional)", "unverified": "Not verified"}


@router.get("/dashboard")
def dashboard(user=Depends(ADMIN), c=Depends(get_c)):
    snap = Snapshot(c)
    open_p = [p for p in snap.pickups if p["status"] not in ("recycled", "cancelled")]
    return {"analytics": analytics(c, snap),
            "queues": {"pickups_open": len(open_p), "to_verify": sum(1 for p in open_p if p["status"] == "picked_up" or (p["mode"] == "dropoff" and p["status"] == "requested")),
                       "fraud_open": sum(1 for f in snap.fraud if f["status"] == "open"), "users": len(snap.users)},
            "audit_recent": sorted(c.store.list(K.AUDIT), key=lambda a: a["at"], reverse=True)[:8]}


@router.get("/users")
def users(user=Depends(ADMIN), c=Depends(get_c)):
    snap = Snapshot(c)
    t = totals(snap)
    return [{"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"], "building": (snap.building(u.get("building_id")) or {}).get("name"),
             "points": t.get(u["id"], {}).get("points", 0), "items": t.get(u["id"], {}).get("items", 0), "created_at": u.get("created_at")}
            for u in sorted(snap.users, key=lambda u: u["name"])]


@router.get("/fraud")
def fraud(user=Depends(ADMIN), c=Depends(get_c)):
    snap = Snapshot(c)
    subs = {s["id"]: s for s in snap.submissions}
    out = []
    for f in sorted(snap.fraud, key=lambda f: (f["status"] != "open", f["created_at"]), reverse=False):
        s = subs.get(f["submission_id"]) or {}
        held = sum(r["points"] for r in snap.ledger if r.get("ref_id") == f["submission_id"] and r["status"] == "held")
        out.append({**f, "item": (s.get("item") or {}).get("label"), "submission_status": s.get("status"), "held_points": held})
    return out


@router.post("/fraud/{fid}/resolve")
def resolve(fid: str, body: ResolveIn, user=Depends(ADMIN), c=Depends(get_c)):
    f = c.store.get(K.FRAUD, fid)
    if not f:
        raise not_found("Flag")
    if f["status"] != "open":
        raise conflict("This flag has already been resolved.", "already_resolved")
    released = 0
    for r in c.store.list(K.LEDGER, owner=f["user_id"]):
        if r.get("ref_id") == f["submission_id"] and r["status"] == "held":
            r["status"] = "posted" if body.action == "approve" else "void"
            released += r["points"] if body.action == "approve" else 0
            c.store.put(K.LEDGER, r["id"], r)
    s = c.store.get(K.SUBMISSIONS, f["submission_id"])
    if s:
        s["fraud"] = {**s["fraud"], "status": "cleared" if body.action == "approve" else "rejected"}
        if s.get("points_status") == "held":
            s["points_status"] = "posted" if body.action == "approve" else "void"
        c.store.put(K.SUBMISSIONS, s["id"], s)
    f.update(status="approved" if body.action == "approve" else "rejected", resolved_by=user["id"], resolved_at=now_iso(), note=body.note)
    c.store.put(K.FRAUD, fid, f)
    if released:
        c.notifier.notify(f["user_id"], "points_released", f"+{released} points released", "Your flagged submission was reviewed and approved.")
    audit(c, user, f"fraud.{body.action}", fid, released=released)
    return {**f, "released_points": released}


@router.post("/verify")
def verify(body: VerifyIn, user=Depends(ADMIN), c=Depends(get_c)):
    return pickups.transition(c, user, body.pickup_id, "verified", body.verified_weight_kg, body.verified_match)


@router.get("/predictions")
def predictions(user=Depends(ADMIN), c=Depends(get_c)):
    subs = {s["id"]: s for s in c.store.list(K.SUBMISSIONS)}
    rows = sorted(c.store.list(K.PREDICTIONS), key=lambda p: p["created_at"], reverse=True)[:100]
    return [{"id": p["id"], "at": p["created_at"], "provider": p["provider"], "model_id": p.get("model_id"), "confidence": (p.get("raw") or {}).get("confidence"),
             "predicted": (p.get("raw") or {}).get("item_type"), "final": (p.get("final") or {}).get("item_type"), "corrected": p.get("corrected"), "correction": p.get("correction"),
             "confirmed": p.get("confirmed"), "user_name": (subs.get(p["submission_id"]) or {}).get("user_name")} for p in rows]


@router.get("/recyclers")
def list_recyclers(user=Depends(ADMIN), c=Depends(get_c)):
    return c.store.list(K.RECYCLERS)


@router.post("/recyclers", status_code=201)
def add_recycler(body: RecyclerIn, user=Depends(ADMIN), c=Depends(get_c)):
    if not (body.name and body.address and body.lat is not None and body.lng is not None and body.accepts):
        raise bad_request("Name, address, location and accepted categories are required.", "missing_fields")
    cats = set(impact_cfg()["categories"])
    if not set(body.accepts) <= cats:
        raise bad_request("Unknown category in 'accepts'.", "bad_category")
    st = body.verification_status or "unverified"
    r = {"id": "r_" + re.sub(r"[^a-z0-9]+", "_", body.name.lower())[:30] + new_id("")[-4:], "name": body.name, "address": body.address, "city": body.city or "", "lat": body.lat, "lng": body.lng,
         "accepts": body.accepts, "hours": body.hours or "", "pickup_available": bool(body.pickup_available), "min_pickup_kg": body.min_pickup_kg or 0, "processing_days": body.processing_days or 7,
         "rating": body.rating or 0, "services": ["recycle"], "demo": False,
         "verification": {"status": st, "label": V_LABEL[st], "source": "Added by admin", "license_no": body.license_no, "valid_until": body.valid_until}}
    c.store.put(K.RECYCLERS, r["id"], r)
    audit(c, user, "recycler.create", r["id"])
    return r


@router.patch("/recyclers/{rid}")
def patch_recycler(rid: str, body: RecyclerIn, user=Depends(ADMIN), c=Depends(get_c)):
    r = c.store.get(K.RECYCLERS, rid)
    if not r:
        raise not_found("Recycler")
    data = body.model_dump(exclude_none=True)
    st = data.pop("verification_status", None)
    lic, until = data.pop("license_no", None), data.pop("valid_until", None)
    r.update(data)
    if st or lic or until:
        v = r.get("verification", {})
        v.update({k: x for k, x in {"status": st, "label": V_LABEL.get(st or ""), "license_no": lic, "valid_until": until}.items() if x})
        r["verification"] = v
    c.store.put(K.RECYCLERS, rid, r)
    audit(c, user, "recycler.update", rid, fields=list(data))
    return r


@router.post("/challenges", status_code=201)
def new_challenge(body: ChallengeIn, user=Depends(require("ADMIN", "ORGANIZATION_ADMIN")), c=Depends(get_c)):
    ch = chl.create(c, user, body.model_dump())
    audit(c, user, "challenge.create", ch["id"], title=ch["title"])
    return ch


@router.post("/points/adjust")
def adjust(body: AdjustIn, user=Depends(ADMIN), c=Depends(get_c)):
    target = c.store.get(K.USERS, body.user_id)
    if not target:
        raise not_found("User")
    row = {"id": new_id("pts"), "user_id": target["id"], "points": body.points, "status": "posted", "reason": f"Admin adjustment: {body.reason}", "ref_type": "admin_adjustment",
           "ref_id": None, "created_at": now_iso(), "meta": {"actor": user["id"]}}
    c.store.put(K.LEDGER, row["id"], row)
    audit(c, user, "points.adjust", target["id"], points=body.points, reason=body.reason)
    c.notifier.notify(target["id"], "points_adjusted", f"{body.points:+d} points adjusted", body.reason)
    return row


@router.get("/audit")
def audit_log(user=Depends(ADMIN), c=Depends(get_c)):
    return sorted(c.store.list(K.AUDIT), key=lambda a: a["at"], reverse=True)[:100]


EXPORTS = {
    "users": (K.USERS, ["id", "name", "email", "role", "org_id", "building_id", "created_at"]),
    "submissions": (K.SUBMISSIONS, ["id", "user_id", "created_at", "status", "item.item_type", "item.condition", "item.quantity", "item.confidence", "item.source", "estimate.impact.weight_kg", "estimate.impact.co2e_kg", "awarded_points", "fraud.status"]),
    "pickups": (K.PICKUPS, ["id", "user_id", "mode", "status", "recycler_name", "date", "slot", "total_kg", "created_at"]),
    "ledger": (K.LEDGER, ["id", "user_id", "points", "status", "reason", "ref_type", "ref_id", "created_at"]),
    "impact": (K.IMPACT, ["id", "user_id", "building_id", "item_type", "category", "quantity", "weight_kg", "co2e_kg", "weight_source", "status", "created_at"]),
}


def _get(d: dict, path: str):
    for part in path.split("."):
        d = d.get(part, "") if isinstance(d, dict) else ""
    return d


def _safe(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s  # CSV/formula-injection guard


@router.get("/export/{kind}")
def export(kind: str, user=Depends(ADMIN), c=Depends(get_c)):
    if kind not in EXPORTS:
        raise bad_request("Unknown export.", "unknown_export")
    store_kind, cols = EXPORTS[kind]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in c.store.list(store_kind):
        w.writerow([_safe(_get(r, col)) for col in cols])
    audit(c, user, "export.csv", kind)
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="reloop_{kind}.csv"'})
