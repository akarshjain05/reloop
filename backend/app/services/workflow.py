"""Submission lifecycle: analyze -> confirm (human in the loop) -> choose action; plus Scan My Waste."""
from __future__ import annotations

import time

from ..ai import agent
from ..ai.mock import MockProvider
from ..ai.types import AIUnavailable
from ..core.errors import conflict, forbidden, not_found
from ..core.logging import log_event
from ..models import kinds as K
from ..repositories.base import new_id, now_iso, parse_ts
from . import fraud
from .catalog import category_label, item_info, normalize_condition, normalize_item_type, scoring_cfg
from .images import prepare_image
from .orgscore import reloop_score
from .stats import Snapshot


def submission_view(c, sub: dict, admin: bool = False) -> dict:
    out = dict(sub)
    img = dict(sub.get("image") or {})
    out["image_url"] = c.storage.url(img["key"]) if img.get("key") else None
    if not admin:
        img.pop("sha256", None)
        img.pop("ahash", None)
    out["image"] = img
    out["category_label"] = category_label(sub["item"]["category"]) if sub.get("item") else None
    return out


def _own(c, user: dict, sid: str, allow_admin: bool = False) -> dict:
    sub = c.store.get(K.SUBMISSIONS, sid)
    if not sub:
        raise not_found("Item")
    if sub["user_id"] != user["id"] and not (allow_admin and user["role"] in ("ADMIN", "COLLECTOR")):
        raise forbidden()
    return sub


def _aws_proof(c, result: dict, stored: dict, total_ms: int, req_ctx: dict) -> dict:
    s = c.settings
    return {
        "ai_provider": result["classification"].get("provider"), "model_id": result["classification"].get("model_id"),
        "bedrock_region": s.bedrock_region if c.ai.name == "bedrock" else None, "agent_mode": result["agent"]["mode"],
        "store": c.store.name, "table": s.dynamodb_table or None, "storage": stored.get("backend"), "bucket": stored.get("bucket"),
        "object_key": stored.get("key"), "lambda_request_id": req_ctx.get("request_id"), "in_lambda": s.in_lambda, "total_ms": total_ms,
    }


def analyze_item(c, user: dict, upload: bytes, filename: str | None, hint: str | None, req_ctx: dict | None = None) -> dict:
    req_ctx = req_ctx or {}
    t0 = time.perf_counter()
    c.limiter.check(f"analyze:{user['id']}", 20, 60)
    img = prepare_image(upload, c.settings.max_upload_mb)
    fraud.enforce_cooldown(c, user)
    fr = fraud.evaluate(c, user, img["sha256"], img["ahash"])

    ai_status, note = "ok", None
    try:
        result = agent.run_workflow(c, user, img["jpeg"], "image/jpeg", filename, hint)
    except AIUnavailable as e:
        log_event("ai_unavailable", user_id=user["id"], provider=c.ai.name, error=str(e)[:200])
        if c.settings.demo_mode and c.ai.name != "mock":
            result = agent.run_workflow(c, user, img["jpeg"], "image/jpeg", filename, hint, ai=MockProvider())
            ai_status, note = "fallback", "Live AI is unavailable, so this is a demo estimate."
        else:
            result = agent.manual_workflow(c, user, hint)
            ai_status, note = "unavailable", "AI analysis is temporarily unavailable. You can select the item manually."

    if result["estimate"] is None:
        log_event("waste_submission", user_id=user["id"], status="no_item", provider=result["classification"].get("provider"))
        return {"ai_status": "no_item", "message": "We couldn't spot an electronic item in that photo. Try a closer, well-lit shot — or pick the item manually.", "submission": None}

    sub_id = new_id("sub")
    stored = c.storage.put(f"uploads/{user['id']}/{sub_id}.jpg", img["jpeg"], "image/jpeg")
    cls, item = result["classification"], result["item"]
    pred = {"id": new_id("prd"), "submission_id": sub_id, "user_id": user["id"], "provider": cls.get("provider"), "model_id": cls.get("model_id"),
            "latency_ms": cls.get("latency_ms"), "raw": cls, "corrected": False, "correction": None, "final": item, "created_at": now_iso(), "confirmed": False}
    total_ms = int((time.perf_counter() - t0) * 1000)
    sub = {"id": sub_id, "user_id": user["id"], "user_name": user["name"], "building_id": user.get("building_id"), "org_id": user.get("org_id"),
           "created_at": now_iso(), "status": "analyzed", "ai_status": ai_status, "prediction_id": pred["id"], "item": item, "estimate": result["estimate"],
           "image": {"key": stored["key"], "bucket": stored.get("bucket"), "backend": stored["backend"], "sha256": img["sha256"], "ahash": img["ahash"],
                     "width": img["width"], "height": img["height"], "size": img["size"]},
           "fraud": fr, "agent": result["agent"], "trace": result["trace"], "aws": _aws_proof(c, result, stored, total_ms, req_ctx), "filename": (filename or "")[:80]}
    c.store.put(K.PREDICTIONS, pred["id"], pred)
    c.store.put(K.SUBMISSIONS, sub_id, sub)
    fraud.register_image(c, img["sha256"], sub_id, user["id"])
    if fr["status"] == "pending_review":
        fraud.open_flag(c, sub, user, fr)
    log_event("waste_submission", user_id=user["id"], category=item["category"], item_type=item["item_type"], confidence=item["confidence"],
              status="analyzed", fraud=fr["status"], provider=cls.get("provider"), ms=total_ms)
    return {"ai_status": ai_status, "message": note, "submission": submission_view(c, sub)}


def confirm(c, user: dict, submission_id: str, corrections: dict | None) -> dict:
    sub = _own(c, user, submission_id)
    if sub["status"] not in ("analyzed", "confirmed"):
        raise conflict("This item is already on its way to recycling, so it can't be edited.", "locked")
    item, corr, changes = dict(sub["item"]), {k: v for k, v in (corrections or {}).items() if v is not None}, {}
    if "item_type" in corr:
        key = normalize_item_type(corr["item_type"])
        if key != item["item_type"]:
            info = item_info(key)
            changes["item_type"] = key
            item.update(item_type=key, label=info["label"], category=info["category"], sub_category=info["sub_category"])
            if "weight_kg" not in corr:
                item["weight_kg"] = None
    if "condition" in corr and normalize_condition(corr["condition"]) != item["condition"]:
        changes["condition"] = item["condition"] = normalize_condition(corr["condition"])
    if "brand" in corr and (corr["brand"] or None) != item.get("brand"):
        changes["brand"] = item["brand"] = corr["brand"] or None
    if "quantity" in corr and int(corr["quantity"]) != item["quantity"]:
        changes["quantity"] = item["quantity"] = int(corr["quantity"])
    if "weight_kg" in corr and corr["weight_kg"] != item.get("weight_kg"):
        changes["weight_kg"] = item["weight_kg"] = float(corr["weight_kg"])
    item["source"] = "user_corrected" if changes else ("manual" if item.get("source") == "manual" else "user_confirmed")

    est = agent.estimate_for_item(c, user, item)
    sub.update(item=item, estimate=est, status="confirmed", confirmed_at=now_iso(), corrected=bool(changes))
    c.store.put(K.SUBMISSIONS, sub["id"], sub)
    pred = c.store.get(K.PREDICTIONS, sub["prediction_id"])
    if pred:
        pred.update(corrected=bool(changes), correction=changes or None, final=item, confirmed=True, confirmed_at=now_iso())
        c.store.put(K.PREDICTIONS, pred["id"], pred)
    log_event("waste_confirmed", user_id=user["id"], item_type=item["item_type"], corrected=bool(changes), fields=list(changes))
    return submission_view(c, sub)


def choose_action(c, user: dict, submission_id: str, action: str) -> dict:
    sub = _own(c, user, submission_id)
    if sub["status"] != "confirmed":
        raise conflict("Confirm the item before choosing what to do with it.", "not_confirmed")
    sub["action_choice"] = action
    c.store.put(K.SUBMISSIONS, sub["id"], sub)
    hint = {"recycle": "Find a recycler or schedule a pickup to earn points once it's verified.",
            "resell": "Reuse avoids the most impact. ReLoop Exchange shows an estimate only — it doesn't list or sell items yet.",
            "repair": "Take it to a repair shop; if it can't be fixed, come back and recycle it.",
            "donate": "Donate it to someone who can use it; recycle it if it no longer works."}[action]
    log_event("waste_action_chosen", user_id=user["id"], action=action, item_type=sub["item"]["item_type"])
    return {**submission_view(c, sub), "action_hint": hint}


def history(c, user: dict) -> list[dict]:
    rows = sorted(c.store.list(K.SUBMISSIONS, owner=user["id"]), key=lambda s: s["created_at"], reverse=True)
    return [submission_view(c, s) for s in rows[:50]]


def get_submission(c, user: dict, sid: str) -> dict:
    sub = _own(c, user, sid, allow_admin=True)
    return submission_view(c, sub, admin=user["role"] in ("ADMIN",))


# ---- Scan My Waste ----------------------------------------------------------------------------------------

def _clean_ratio(categories: list[dict]) -> float:
    flagged = sum(1 for x in categories if x["present"] and x["key"] in ("e_waste", "hazardous") and not x.get("fixed"))
    return {0: 1.0, 1: 0.5}.get(flagged, 0.0)


def bin_scan(c, user: dict, upload: bytes, filename: str | None, req_ctx: dict | None = None) -> dict:
    c.limiter.check(f"bin:{user['id']}", 10, 60)
    img = prepare_image(upload, c.settings.max_upload_mb)
    duplicate = bool(c.store.get(K.IMG_IDX, img["sha256"]))
    ai_status, note = "ok", None
    try:
        res = c.ai.analyze_bin(img["jpeg"], "image/jpeg", filename)
    except AIUnavailable as e:
        log_event("ai_unavailable", user_id=user["id"], provider=c.ai.name, error=str(e)[:200], feature="bin_scan")
        if c.settings.demo_mode:
            res, ai_status, note = MockProvider().analyze_bin(img["jpeg"], "image/jpeg", filename), "fallback", "Live AI is unavailable, so this is a demo result."
        else:
            from ..ai.types import BinAnalysis, bin_advice, build_bin_categories
            cats = build_bin_categories({})
            res, ai_status, note = BinAnalysis(categories=cats, advice=bin_advice(cats), provider="manual", model_id="none"), "unavailable", \
                "AI analysis is temporarily unavailable. Tick the categories you can see."
    scan = {"id": new_id("bin"), "user_id": user["id"], "building_id": user.get("building_id"), "org_id": user.get("org_id"), "created_at": now_iso(),
            "categories": res.categories, "advice": res.advice, "provider": res.provider, "model_id": res.model_id, "confirmed": False,
            "clean_ratio": _clean_ratio(res.categories), "duplicate": duplicate, "ai_status": ai_status}
    c.store.put(K.BIN_SCANS, scan["id"], scan)
    fraud.register_image(c, img["sha256"], scan["id"], user["id"])
    log_event("bin_scan", user_id=user["id"], provider=res.provider, duplicate=duplicate)
    return {**scan, "message": note}


def bin_confirm(c, user: dict, scan_id: str, present: dict | None, removed: list | None = None) -> dict:
    scan = c.store.get(K.BIN_SCANS, scan_id)
    if not scan or scan["user_id"] != user["id"]:
        raise not_found("Bin check")
    if scan["confirmed"]:
        raise conflict("You already confirmed this check.", "already_confirmed")
    before = reloop_score(c, "building", user["building_id"])["score"] if user.get("building_id") else None
    if present:
        for x in scan["categories"]:
            if x["key"] in present:
                x["present"] = bool(present[x["key"]])
                x["status"] = "warn" if (x["present"] and x["key"] in ("e_waste", "hazardous")) else ("ok" if x["present"] else "absent")
    for x in scan["categories"]:  # the person acted on the nudge: they took the flagged items out before disposal
        if x["key"] in (removed or []) and x["present"] and x["key"] in ("e_waste", "hazardous"):
            x["fixed"], x["status"] = True, "fixed"
    scan["clean_ratio"] = _clean_ratio(scan["categories"])
    scan.update(confirmed=True, confirmed_at=now_iso())
    cfg = scoring_cfg()["points"]
    recent = [r for r in c.store.list(K.LEDGER, owner=user["id"]) if r.get("ref_type") == "bin_scan" and
              (time.time() - parse_ts(r["created_at"]).timestamp()) < cfg["bin_scan_cooldown_hours"] * 3600]
    awarded = 0
    if not scan["duplicate"] and not recent and scan["provider"] != "manual":
        awarded = cfg["bin_scan_points"]
        rid = new_id("pts")
        c.store.put(K.LEDGER, rid, {"id": rid, "user_id": user["id"], "points": awarded, "status": "posted", "reason": "Confirmed waste segregation check",
                                    "ref_type": "bin_scan", "ref_id": scan["id"], "created_at": now_iso(), "meta": {}})
    scan["points_awarded"] = awarded
    c.store.put(K.BIN_SCANS, scan["id"], scan)
    after = reloop_score(c, "building", user["building_id"])["score"] if user.get("building_id") else None
    if awarded:
        c.notifier.notify(user["id"], "points_earned", f"+{awarded} points for checking your bin", "Segregation checks improve your building's score.")
    return {**scan, "building_score_before": before, "building_score_after": after}
