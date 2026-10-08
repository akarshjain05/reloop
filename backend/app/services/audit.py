from __future__ import annotations

from ..core.logging import log_event
from ..models import kinds as K
from ..repositories.base import new_id, now_iso


def audit(c, actor: dict, action: str, target: str, **meta) -> None:
    row = {"id": new_id("aud"), "actor_id": actor.get("id"), "actor_name": actor.get("name"), "actor_role": actor.get("role"),
           "action": action, "target": target, "at": now_iso(), "meta": meta}
    c.store.put(K.AUDIT, row["id"], row)
    log_event("audit", actor_id=actor.get("id"), action=action, target=target)
