from __future__ import annotations

from ..core.config import Settings
from .bedrock import BedrockProvider
from .mock import MockProvider
from .types import AIProvider


def make_ai(s: Settings) -> AIProvider:
    if s.ai_kind == "bedrock":
        return BedrockProvider(s.bedrock_model_id, s.bedrock_region)
    return MockProvider()
