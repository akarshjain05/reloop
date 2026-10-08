from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..models.schemas import PickupIn, StatusIn
from ..services import pickups as svc
from .deps import current_user, get_c

router = APIRouter(tags=["pickups"])


@router.get("/pickups/slots")
def slots():
    return {"slots": svc.SLOTS}


@router.post("/pickups", status_code=201)
def create(body: PickupIn, user=Depends(current_user), c=Depends(get_c)):
    return svc.create_pickup(c, user, body.model_dump())


@router.get("/pickups")
def list_(status: str | None = Query(default=None, max_length=30), user=Depends(current_user), c=Depends(get_c)):
    return svc.list_pickups(c, user, status)


@router.get("/pickups/{pid}")
def get_one(pid: str, user=Depends(current_user), c=Depends(get_c)):
    return svc.get_pickup(c, user, pid)


@router.patch("/pickups/{pid}/status")
def set_status(pid: str, body: StatusIn, user=Depends(current_user), c=Depends(get_c)):
    return svc.transition(c, user, pid, body.status, body.verified_weight_kg, body.verified_match, body.note, body.collector_id)


@router.post("/pickups/{pid}/fast-forward")
def fast_forward(pid: str, user=Depends(current_user), c=Depends(get_c)):
    return svc.fast_forward(c, user, pid)
