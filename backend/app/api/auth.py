from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..core.security import public_user
from ..models.schemas import LoginIn, RegisterIn
from .deps import current_user, get_c

router = APIRouter(tags=["auth"])


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request, c=Depends(get_c)):
    c.limiter.check(f"register:{request.client.host if request.client else 'x'}", 10, 60)
    return c.auth.register(c, body.email, body.password, body.name.strip(), body.building_id)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, c=Depends(get_c)):
    c.limiter.check(f"login:{request.client.host if request.client else 'x'}:{body.email.lower()}", 8, 60)
    return c.auth.login(c, body.email, body.password)


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return public_user(user)
