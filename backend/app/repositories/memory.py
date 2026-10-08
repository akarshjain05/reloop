from __future__ import annotations

import copy
import threading

from .base import Store


class MemoryStore(Store):
    """Process-local store used for local development, demos and tests."""

    name = "memory"

    def __init__(self) -> None:
        self._d: dict[str, dict[str, dict]] = {}
        self._lock = threading.RLock()

    def put(self, kind, id, doc):
        with self._lock:
            self._d.setdefault(kind, {})[id] = copy.deepcopy(doc)
        return doc

    def get(self, kind, id):
        with self._lock:
            d = self._d.get(kind, {}).get(id)
            return copy.deepcopy(d) if d is not None else None

    def list(self, kind, owner=None):
        with self._lock:
            rows = [d for _, d in sorted(self._d.get(kind, {}).items())]
            if owner is not None:
                rows = [d for d in rows if d.get("user_id") == owner]
            return copy.deepcopy(rows)

    def delete(self, kind, id):
        with self._lock:
            self._d.get(kind, {}).pop(id, None)

    def is_empty(self):
        with self._lock:
            return not any(self._d.values())
