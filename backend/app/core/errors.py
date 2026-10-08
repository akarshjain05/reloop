from __future__ import annotations


class AppError(Exception):
    """Domain error rendered as {"error": {"code", "message"}} by the API layer."""

    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


def bad_request(message: str, code: str = "bad_request", **extra) -> AppError:
    return AppError(400, code, message, **extra)


def unauthorized(message: str = "Please sign in to continue.") -> AppError:
    return AppError(401, "unauthorized", message)


def forbidden(message: str = "You don't have access to this.") -> AppError:
    return AppError(403, "forbidden", message)


def not_found(what: str = "Item") -> AppError:
    return AppError(404, "not_found", f"{what} not found.")


def conflict(message: str, code: str = "conflict", **extra) -> AppError:
    return AppError(409, code, message, **extra)


def too_many(message: str, retry_after: int = 5) -> AppError:
    return AppError(429, "rate_limited", message, retry_after=retry_after)
