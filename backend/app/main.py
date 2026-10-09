from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import admin, advisor, auth, community, market, me, pickups, system, waste
from .core.config import Settings, get_settings
from .core.container import build_container
from .core.errors import AppError
from .core.logging import log_event, logger, setup_logging
from .services.seed import seed_demo

DESCRIPTION = """ReLoop API — turn e-waste into value. Photograph an item, confirm what the AI saw, get an estimated value and impact,
then recycle through a verified pickup or drop-off to earn points. All values are **estimates**; prices come from a market dataset."""


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()
    setup_logging()
    app = FastAPI(title="ReLoop API", version=system.VERSION, description=DESCRIPTION, docs_url="/docs", redoc_url=None)
    app.state.c = build_container(s)
    if s.should_seed:
        res = seed_demo(app.state.c)
        log_event("demo_seed", **res)
    log_event("startup", demo_mode=s.demo_mode, ai=app.state.c.ai.name, store=app.state.c.store.name, storage=app.state.c.storage.kind, auth=app.state.c.auth.kind)

    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type"], allow_credentials=False, max_age=600)

    @app.middleware("http")
    async def secure_and_log(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"})
        if not request.url.path.startswith("/media/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if request.url.path != "/health":
            log_event("request", method=request.method, path=request.url.path, status=response.status_code, ms=int((time.perf_counter() - t0) * 1000),
                      user_id=getattr(request.state, "user_id", None))
        return response

    @app.exception_handler(AppError)
    async def on_app_error(request: Request, e: AppError):
        headers = {"Retry-After": str(e.extra["retry_after"])} if "retry_after" in e.extra else None
        return JSONResponse({"error": {"code": e.code, "message": e.message, **e.extra}}, status_code=e.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, e: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]} for err in e.errors()]
        return JSONResponse({"error": {"code": "invalid_request", "message": "Some details look wrong. Please check them and try again.", "fields": fields}}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def on_http(request: Request, e: StarletteHTTPException):
        return JSONResponse({"error": {"code": "http_error", "message": "That page doesn't exist." if e.status_code == 404 else str(e.detail)}}, status_code=e.status_code)

    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, e: Exception):
        logger.exception("unhandled_error", extra={"fields": {"event": "unhandled_error", "path": request.url.path, "error": type(e).__name__}})
        return JSONResponse({"error": {"code": "server_error", "message": "Something went wrong on our side. Please try again."}}, status_code=500)

    for r in (system.router, auth.router, waste.router, market.router, pickups.router, community.router, me.router, advisor.router, admin.router):
        app.include_router(r)
    return app


_app: FastAPI | None = None


def __getattr__(name: str):
    """Lazy `app` so `uvicorn app.main:app` works without importing this module creating state (tests, tooling)."""
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)
