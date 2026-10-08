from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ..models.schemas import ActionIn, ConfirmIn
from ..services import workflow
from ..services.catalog import CONDITION_LABELS, category_label, factors
from .deps import current_user, get_c, req_ctx

router = APIRouter(tags=["waste"])


def _read(c, image: UploadFile) -> bytes:
    return image.file.read(c.settings.max_upload_mb * 1024 * 1024 + 1)


def _name(image: UploadFile) -> str:
    return os.path.basename(image.filename or "")[:80]


@router.get("/waste/options")
def options():
    return {"items": [{"key": k, "label": v["label"], "category": v["category"], "category_label": category_label(v["category"]), "hazardous": v["hazardous"]} for k, v in factors().items()],
            "conditions": [{"key": k, "label": v} for k, v in CONDITION_LABELS.items()]}


@router.post("/waste/analyze")
def analyze(request: Request, image: UploadFile = File(...), hint: str | None = Form(default=None), user=Depends(current_user), c=Depends(get_c)):
    clean_hint = re.sub(r"[^\w \-]", "", hint or "")[:40].strip() or None
    return workflow.analyze_item(c, user, _read(c, image), _name(image), clean_hint, req_ctx(request))


@router.post("/waste/confirm")
def confirm(body: ConfirmIn, user=Depends(current_user), c=Depends(get_c)):
    return workflow.confirm(c, user, body.submission_id, body.corrections.model_dump(exclude_none=True) if body.corrections else None)


@router.get("/waste/history")
def history(user=Depends(current_user), c=Depends(get_c)):
    return workflow.history(c, user)


@router.post("/waste/bin-scan")
def bin_scan(request: Request, image: UploadFile = File(...), user=Depends(current_user), c=Depends(get_c)):
    return workflow.bin_scan(c, user, _read(c, image), _name(image), req_ctx(request))


@router.post("/waste/bin-scan/{scan_id}/confirm")
def bin_confirm(scan_id: str, body: dict | None = None, user=Depends(current_user), c=Depends(get_c)):
    present, removed = (body or {}).get("present"), (body or {}).get("removed")
    return workflow.bin_confirm(c, user, scan_id, present if isinstance(present, dict) else None,
                                [str(k) for k in removed][:6] if isinstance(removed, list) else None)


@router.get("/waste/{submission_id}")
def get_one(submission_id: str, user=Depends(current_user), c=Depends(get_c)):
    return workflow.get_submission(c, user, submission_id)


@router.post("/waste/{submission_id}/action")
def action(submission_id: str, body: ActionIn, user=Depends(current_user), c=Depends(get_c)):
    return workflow.choose_action(c, user, submission_id, body.action)
