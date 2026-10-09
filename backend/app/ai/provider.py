from __future__ import annotations

from ..core.config import Settings
from .rekognition import RekognitionProvider
from .mock import MockProvider
from .types import AIProvider


def make_ai(s: Settings) -> AIProvider:
    if s.ai_kind == "bedrock":
        return RekognitionProvider(s.aws_region)
    return MockProvider()
