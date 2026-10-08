"""Notification abstraction: add an email/SMS/push Channel without touching callers."""
from __future__ import annotations

from typing import Protocol

from ..core.logging import log_event
from ..models import kinds as K
from ..repositories.base import Store, new_id, now_iso


class Channel(Protocol):
    def send(self, notification: dict) -> None: ...


class InAppChannel:
    def __init__(self, store: Store) -> None:
        self.store = store

    def send(self, n: dict) -> None:
        self.store.put(K.NOTIFS, n["id"], n)


class LogChannel:
    def send(self, n: dict) -> None:
        log_event("notification", user_id=n["user_id"], type=n["type"])


class Notifier:
    def __init__(self, store: Store, channels: list[Channel] | None = None) -> None:
        self.channels = channels or [InAppChannel(store), LogChannel()]

    def notify(self, user_id: str, type: str, title: str, body: str = "", **meta) -> dict:
        n = {"id": new_id("ntf"), "user_id": user_id, "type": type, "title": title, "body": body,
             "created_at": now_iso(), "read": False, "meta": meta}
        for ch in self.channels:
            try:
                ch.send(n)
            except Exception as e:  # a failing channel must never break the main flow
                log_event("notification_channel_failed", channel=type(ch).__name__, error=str(e)[:120])
        return n
