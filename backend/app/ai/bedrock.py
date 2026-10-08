"""Amazon Bedrock provider (Converse API, multimodal). Output is forced into a strict JSON contract and validated."""
from __future__ import annotations

import json
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..services.catalog import CONDITIONS, item_info, item_types, normalize_condition, normalize_item_type
from .types import AIProvider, AIUnavailable, BinAnalysis, ItemAnalysis, bin_advice, build_bin_categories

ITEM_SYSTEM = (
    "You are the WasteLens vision module of ReLoop, an e-waste recycling app. "
    "You identify electronic items from photos. You never guess prices."
)


def _item_prompt(hint: str | None) -> str:
    types = ", ".join(item_types())
    extra = f"\nThe user suggests it may be: {hint}. Treat that as a weak hint only." if hint else ""
    return (
        "Identify the main electronic item in this photo. Respond with ONLY a JSON object (no prose, no markdown) with keys:\n"
        f'"item_type": one of [{types}, "not_electronics"],\n'
        '"label": short human-readable name,\n'
        '"brand": string or null,\n'
        f'"condition": one of {list(CONDITIONS)} (judge only from what is visible; if unsure use "good" with lower confidence),\n'
        '"confidence": number from 0 to 1,\n'
        '"quantity": integer count of identical items visible (1-20),\n'
        '"notes": one short sentence about visible condition or uncertainty.\n'
        'Use "not_electronics" if no electronic item is visible. If unsure between types pick the closest and lower the confidence.'
        + extra
    )


BIN_SYSTEM = "You are the waste-segregation checker of ReLoop. You look at photos of waste bins or piles."
BIN_PROMPT = (
    "Which waste categories are present? Respond with ONLY JSON: "
    '{"categories": {"plastic": {"present": bool, "confidence": 0-1, "note": str}, "paper": {...}, "metal": {...}, '
    '"organic": {...}, "e_waste": {...}, "hazardous": {...}}}. '
    '"e_waste" = electronics, cables, chargers, devices. "hazardous" = loose batteries, chemicals, bulbs, aerosols, medical waste. '
    "Each note is at most 12 words."
)


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AIUnavailable("model did not return JSON")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise AIUnavailable(f"model returned invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise AIUnavailable("model JSON was not an object")
    return data


class BedrockProvider(AIProvider):
    name = "bedrock"
    supports_chat = True

    def __init__(self, model_id: str, region: str, client=None) -> None:
        self.model_id = model_id
        self.region = region
        self.client = client or boto3.client(
            "bedrock-runtime", region_name=region,
            config=Config(read_timeout=25, connect_timeout=5, retries={"max_attempts": 2, "mode": "standard"}),
        )

    def _converse(self, system: str, messages: list[dict], max_tokens: int = 700) -> str:
        try:
            resp = self.client.converse(
                modelId=self.model_id, system=[{"text": system}], messages=messages,
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0.1},
            )
            blocks = resp["output"]["message"]["content"]
            return "".join(b.get("text", "") for b in blocks)
        except (ClientError, BotoCoreError, KeyError) as e:
            raise AIUnavailable(f"bedrock call failed: {type(e).__name__}: {e}") from e

    @staticmethod
    def _image_block(image: bytes) -> dict:
        return {"image": {"format": "jpeg", "source": {"bytes": image}}}  # the API re-encodes uploads to JPEG first

    def analyze_item(self, image, content_type, filename=None, hint=None) -> ItemAnalysis:
        t0 = time.perf_counter()
        text = self._converse(ITEM_SYSTEM, [{"role": "user", "content": [self._image_block(image), {"text": _item_prompt(hint)}]}])
        data = parse_json(text)
        raw_type = str(data.get("item_type", "")).strip().lower()
        electronics = raw_type != "not_electronics"
        item_type = normalize_item_type(raw_type) if electronics else "other_electronics"
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
            quantity = max(1, min(20, int(data.get("quantity", 1) or 1)))
        except (TypeError, ValueError) as e:
            raise AIUnavailable("model returned non-numeric confidence/quantity") from e
        brand = data.get("brand")
        return ItemAnalysis(
            item_type=item_type, label=str(data.get("label") or item_info(item_type)["label"])[:60], confidence=round(confidence, 2),
            condition=normalize_condition(data.get("condition")), brand=(str(brand)[:40] if brand else None), quantity=quantity,
            notes=str(data.get("notes") or "")[:200], electronics=electronics, provider=self.name, model_id=self.model_id,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    def analyze_bin(self, image, content_type, filename=None) -> BinAnalysis:
        t0 = time.perf_counter()
        text = self._converse(BIN_SYSTEM, [{"role": "user", "content": [self._image_block(image), {"text": BIN_PROMPT}]}])
        cats_raw = parse_json(text).get("categories")
        if not isinstance(cats_raw, dict):
            raise AIUnavailable("model JSON missing categories")
        present = {}
        for key, v in cats_raw.items():
            if isinstance(v, dict):
                present[key] = (bool(v.get("present")), float(v.get("confidence", 0.5) or 0.5), str(v.get("note") or "")[:80])
        cats = build_bin_categories(present)
        return BinAnalysis(categories=cats, advice=bin_advice(cats), provider=self.name, model_id=self.model_id,
                           latency_ms=int((time.perf_counter() - t0) * 1000))

    def chat(self, system: str, messages: list[dict]) -> str:
        conv = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages if m.get("role") in ("user", "assistant")]
        if not conv or conv[0]["role"] != "user":
            raise AIUnavailable("conversation must start with a user message")
        return self._converse(system, conv, max_tokens=500).strip()
