from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPBearer

from ..core.errors import forbidden, unauthorized

bearer = HTTPBearer(auto_error=False)


def get_c(request: Request):
    return request.app.state.c


def current_user(request: Request, creds=Depends(bearer), c=Depends(get_c)) -> dict:
    if not creds or not creds.credentials:
        raise unauthorized()
    user = c.auth.authenticate(c, creds.credentials)
    request.state.user_id = user["id"]
    return user


def require(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise forbidden("This area is for authorised staff only.")
        return user

    return dep


def req_ctx(request: Request) -> dict:
    """Surfaces the Lambda request id (when running behind API Gateway) for the in-app AWS proof panel."""
    ctx = request.scope.get("aws.context")
    return {"request_id": getattr(ctx, "aws_request_id", None)}
