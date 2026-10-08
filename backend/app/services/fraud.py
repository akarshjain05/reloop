"""Basic anti-abuse: exact + perceptual duplicate detection, cooldown, velocity, admin review queue."""
from __future__ import annotations

from datetime import timedelta

from ..models import kinds as K
from ..repositories.base import new_id, now_iso, parse_ts
from ..core.errors import too_many
from .catalog import scoring_cfg
from .images import hamming
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enforce_cooldown(c, user: dict) -> None:
    last = max((parse_ts(s["created_at"]) for s in c.store.list(K.SUBMISSIONS, owner=user["id"])), default=None)
    wait = c.settings.submission_cooldown_seconds
    if last and (_now() - last).total_seconds() < wait:
        left = max(1, int(wait - (_now() - last).total_seconds()) + 1)
        raise too_many(f"Nice and steady — please wait {left}s before scanning the next item.", retry_after=left)


def evaluate(c, user: dict, sha256: str, ahash: str) -> dict:
    cfg = scoring_cfg()["fraud"]
    flags: list[dict] = []
    mine = c.store.list(K.SUBMISSIONS, owner=user["id"])

    prior = c.store.get(K.IMG_IDX, sha256)
    if prior:
        flags.append({"code": "DUPLICATE_EXACT", "score": cfg["scores"]["duplicate_exact"],
                      "detail": "This exact image was already submitted" + (" by you." if prior.get("submitter") == user["id"] else ".")})
    else:
        for s in mine[-50:]:
            h = (s.get("image") or {}).get("ahash")
            if h and hamming(h, ahash) <= cfg["near_duplicate_hamming"]:
                flags.append({"code": "DUPLICATE_SIMILAR", "score": cfg["scores"]["duplicate_similar"],
                              "detail": "A very similar image was previously submitted."})
                break

    hour_ago = _now() - timedelta(hours=1)
    if sum(1 for s in mine if parse_ts(s["created_at"]) > hour_ago) >= cfg["velocity_limit_per_hour"]:
        flags.append({"code": "HIGH_VELOCITY", "score": cfg["scores"]["high_velocity"], "detail": "Unusually many submissions in the last hour."})

    score = min(100, sum(f["score"] for f in flags))
    status = "pending_review" if score >= cfg["review_threshold"] else "ok"
    return {"score": score, "flags": flags, "status": status}


def register_image(c, sha256: str, submission_id: str, user_id: str) -> None:
    if not c.store.get(K.IMG_IDX, sha256):
        c.store.put(K.IMG_IDX, sha256, {"submission_id": submission_id, "submitter": user_id, "created_at": now_iso()})


def open_flag(c, submission: dict, user: dict, result: dict, extra_reason: str | None = None) -> dict:
    flag = {
        "id": new_id("flg"), "submission_id": submission["id"], "user_id": user["id"], "user_name": user.get("name"),
        "score": result["score"], "reasons": [f["code"] for f in result["flags"]] + ([extra_reason] if extra_reason else []),
        "details": [f["detail"] for f in result["flags"]], "status": "open", "created_at": now_iso(),
        "message": "Suspicious submission detected — pending verification.",
    }
    c.store.put(K.FRAUD, flag["id"], flag)
    return flag


def open_flags_for(c, submission_id: str) -> list[dict]:
    return [f for f in c.store.list(K.FRAUD) if f["submission_id"] == submission_id and f["status"] == "open"]
