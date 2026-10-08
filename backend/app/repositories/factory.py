from __future__ import annotations

from ..core.config import Settings
from .base import Store
from .dynamo import DynamoStore
from .memory import MemoryStore


def make_store(s: Settings) -> Store:
    if s.store_kind == "dynamodb":
        return DynamoStore(s.dynamodb_table, s.aws_region)
    return MemoryStore()
