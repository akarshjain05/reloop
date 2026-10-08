from __future__ import annotations

from dataclasses import dataclass, field

from ..ai.provider import make_ai
from ..ai.types import AIProvider
from ..repositories.base import Store
from ..repositories.factory import make_store
from ..services.notifications import Notifier
from ..services.pricing import CuratedPriceProvider, PriceProvider
from ..services.storage import ImageStorage, make_storage
from .config import Settings
from .ratelimit import RateLimiter
from .security import AuthProvider, make_auth


@dataclass
class Container:
    settings: Settings
    store: Store
    storage: ImageStorage
    ai: AIProvider
    prices: PriceProvider
    notifier: Notifier
    auth: AuthProvider
    limiter: RateLimiter = field(default_factory=RateLimiter)


def build_container(s: Settings) -> Container:
    store = make_store(s)
    return Container(settings=s, store=store, storage=make_storage(s), ai=make_ai(s), prices=CuratedPriceProvider(),
                     notifier=Notifier(store), auth=make_auth(s))
