import json

import pytest

from app.ai.bedrock import BedrockProvider, parse_json
from app.ai.mock import MockProvider
from app.ai.types import AIUnavailable
from conftest import auth, make_image, upload


def test_mock_is_deterministic_and_uses_filename_hint():
    m = MockProvider()
    a, b = m.analyze_item(make_image(3), "image/jpeg", "laptop.jpg"), m.analyze_item(make_image(3), "image/jpeg", "laptop.jpg")
    assert a == b and a.item_type == "laptop" and 0.5 < a.confidence <= 1
    assert m.analyze_item(make_image(3), "image/jpeg", "cracked-macbook.jpg").condition == "damaged"
    assert "not computer vision" in a.notes  # the mock is explicit about what it is


def test_mock_without_hint_still_returns_a_catalog_item():
    r = MockProvider().analyze_item(make_image(9), "image/jpeg", "IMG_0001.jpg")
    assert r.item_type and r.provider == "mock"


def test_analyze_response_has_the_documented_summary_shape(client):
    h = auth(client)
    r = upload(client, h, "laptop.jpg", seed=11)
    assert r.status_code == 200
    s = r.json()["submission"]["estimate"]["summary"]
    for key in ("item", "category", "sub_category", "condition", "confidence", "recommended_action", "estimated_value_min", "estimated_value_max",
                "estimated_weight_kg", "estimated_recovery_score", "estimated_co2_avoidance_kg", "recommended_disposal", "points"):
        assert key in s
    assert s["is_estimate"] is True and "confirm item and condition" in s["note"]
    assert r.json()["submission"]["agent"]["mode"] == "pipeline"
    assert [t["tool"] for t in r.json()["submission"]["trace"]][0] == "identify_waste"


class FakeBedrock:
    def __init__(self, text):
        self.text, self.calls = text, []

    def converse(self, **kw):
        self.calls.append(kw)
        return {"output": {"message": {"content": [{"text": self.text}]}}}


def test_bedrock_provider_parses_fenced_json_and_sends_image_block():
    payload = {"item_type": "Laptop", "label": "Dell laptop", "brand": "Dell", "condition": "fair", "confidence": 1.4, "quantity": 2, "notes": "scuffed lid"}
    fake = FakeBedrock("Sure!\n```json\n" + json.dumps(payload) + "\n```")
    r = BedrockProvider("test-model", "us-east-1", client=fake).analyze_item(b"\xff\xd8\xff-jpeg", "image/jpeg", hint="old laptop")
    assert (r.item_type, r.condition, r.brand, r.quantity) == ("laptop", "fair", "Dell", 2) and r.confidence == 1.0 and r.provider == "bedrock"
    call = fake.calls[0]
    assert call["modelId"] == "test-model" and call["messages"][0]["content"][0]["image"]["format"] == "jpeg"
    assert "old laptop" in call["messages"][0]["content"][1]["text"]


def test_bedrock_provider_flags_non_electronics_and_rejects_garbage():
    r = BedrockProvider("m", "r", client=FakeBedrock('{"item_type": "not_electronics", "confidence": 0.9}')).analyze_item(b"x", "image/jpeg")
    assert r.electronics is False
    with pytest.raises(AIUnavailable):
        BedrockProvider("m", "r", client=FakeBedrock("I can't help with that")).analyze_item(b"x", "image/jpeg")
    with pytest.raises(AIUnavailable):
        parse_json("[1, 2, 3]")


def test_bedrock_failure_surfaces_as_ai_unavailable():
    class Boom:
        def converse(self, **kw):
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "Converse")

    with pytest.raises(AIUnavailable):
        BedrockProvider("m", "r", client=Boom()).analyze_item(b"x", "image/jpeg")


def test_ai_outage_in_demo_mode_falls_back_but_says_so(app, client, monkeypatch):
    def broken(*a, **k):
        raise AIUnavailable("down")

    h = auth(client)
    app.state.c.ai = BedrockProvider("m", "r", client=FakeBedrock("nope"))
    r = upload(client, h, "laptop.jpg", seed=21)
    assert r.status_code == 200 and r.json()["ai_status"] == "fallback" and "unavailable" in r.json()["message"]


def test_ai_outage_without_demo_mode_lets_the_user_pick_manually(app, client):
    h = auth(client)
    app.state.c.settings.demo_mode = False
    app.state.c.ai = BedrockProvider("m", "r", client=FakeBedrock("nope"))
    r = upload(client, h, "x.jpg", seed=22, hint="router")
    j = r.json()
    assert j["ai_status"] == "unavailable" and "select the item manually" in j["message"]
    assert j["submission"]["item"]["item_type"] == "router" and j["submission"]["item"]["source"] == "manual"


def test_strands_tools_register_with_specs(c):
    from strands import tool
    from app.ai.agent import ToolContext, build_tools
    ctx = ToolContext(c, {"id": "u_demo", "building_id": "b_hostel_a"})
    names = [tool(f).tool_spec["name"] for f in build_tools(ctx).values()]
    assert names == ["identify_waste", "get_price_estimate", "get_recycler_options", "calculate_environmental_impact", "calculate_points", "get_user_history", "recommend_next_action"]
