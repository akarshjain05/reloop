"""Storage abstraction. One generic document store with two adapters (memory, DynamoDB).

Documents are plain dicts. `kind` is the logical table (users, waste_submissions, ...).
If a document carries `user_id` it is indexed by owner for cheap per-user listing.
"""
from __future__ import annotations

import secrets
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


def new_id(prefix: str) -> str:
    """Time-sortable id: prefix + ms timestamp (hex) + random suffix."""
    return f"{prefix}_{int(time.time() * 1000):011x}{secrets.token_hex(3)}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def days_ago(days: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


class Store(ABC):
    name = "abstract"

    @abstractmethod
    def put(self, kind: str, id: str, doc: dict) -> dict: ...

    @abstractmethod
    def get(self, kind: str, id: str) -> dict | None: ...

    @abstractmethod
    def list(self, kind: str, owner: str | None = None) -> list[dict]: ...

    @abstractmethod
    def delete(self, kind: str, id: str) -> None: ...

    @abstractmethod
    def is_empty(self) -> bool: ...

    def put_many(self, items: list[tuple[str, str, dict]]) -> None:
        for kind, id, doc in items:
            self.put(kind, id, doc)

    def update(self, kind: str, id: str, **fields) -> dict:
        doc = self.get(kind, id)
        if doc is None:
            raise KeyError(f"{kind}/{id}")
        doc.update(fields)
        return self.put(kind, id, doc)
