from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models.schemas import AdvisorIn
from ..services import advisor
from .deps import current_user, get_c

router = APIRouter(tags=["advisor"])


@router.post("/advisor/chat")
def chat(body: AdvisorIn, user=Depends(current_user), c=Depends(get_c)):
    return advisor.answer(c, user, body.message.strip(), body.history)
