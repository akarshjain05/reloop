"""CloudWatch-friendly structured JSON logging. Never logs credentials."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_SENSITIVE = {"password", "token", "authorization", "secret", "access_token", "id_token", "refresh_token"}
logger = logging.getLogger("reloop")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        else:
            payload["message"] = record.getMessage()
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:  # e.g. the Lambda runtime handler
        for h in root.handlers:
            h.setFormatter(JsonFormatter())
    else:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JsonFormatter())
        root.addHandler(h)
    for noisy in ("botocore", "boto3", "urllib3", "uvicorn.access", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(event: str, **fields) -> None:
    clean = {k: ("[redacted]" if k.lower() in _SENSITIVE else v) for k, v in fields.items()}
    logger.info(event, extra={"fields": {"event": event, **clean}})
