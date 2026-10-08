from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

BIN_CATEGORIES = [
    ("plastic", "Plastic"), ("paper", "Paper"), ("metal", "Metal"),
    ("organic", "Organic"), ("e_waste", "E-Waste"), ("hazardous", "Hazardous"),
]
_WARN = {"e_waste", "hazardous"}


class AIUnavailable(Exception):
    """Raised when the AI provider can't produce a usable answer (network, throttling, bad output)."""


@dataclass
class ItemAnalysis:
    item_type: str
    label: str
    confidence: float
    condition: str = "good"
    brand: str | None = None
    quantity: int = 1
    notes: str = ""
    electronics: bool = True
    provider: str = "mock"
    model_id: str = "reloop-mock-v1"
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BinAnalysis:
    categories: list[dict] = field(default_factory=list)
    advice: str = ""
    provider: str = "mock"
    model_id: str = "reloop-mock-v1"
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def build_bin_categories(present: dict[str, tuple[bool, float, str]]) -> list[dict]:
    out = []
    for key, label in BIN_CATEGORIES:
        is_present, conf, note = present.get(key, (False, 0.5, ""))
        out.append({
            "key": key, "label": label, "present": bool(is_present), "confidence": round(float(conf), 2), "note": note,
            "status": "warn" if (is_present and key in _WARN) else ("ok" if is_present else "absent"),
        })
    return out


def bin_advice(categories: list[dict]) -> str:
    present = {c["key"] for c in categories if c["present"]}
    tips = []
    if "e_waste" in present:
        tips.append("Remove the battery and electronic components before disposing of the remaining waste.")
    if "hazardous" in present:
        tips.append("Keep hazardous items (loose batteries, bulbs, chemicals) out of general waste and take them to a hazardous-waste drop-off.")
    return " ".join(tips) or "Nice — no e-waste or hazardous items spotted. Keep segregating plastic, paper, metal and organic waste."


class AIProvider(ABC):
    name = "abstract"
    model_id = "n/a"
    supports_chat = False

    @abstractmethod
    def analyze_item(self, image: bytes, content_type: str, filename: str | None = None, hint: str | None = None) -> ItemAnalysis: ...

    @abstractmethod
    def analyze_bin(self, image: bytes, content_type: str, filename: str | None = None) -> BinAnalysis: ...

    def chat(self, system: str, messages: list[dict]) -> str:
        raise AIUnavailable(f"{self.name} provider has no language model")
