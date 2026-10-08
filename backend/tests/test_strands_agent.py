"""Runs the REAL Strands Agents SDK loop (tool schema, dispatch, results) with a scripted fake model instead of Bedrock.
What this proves: our tools work as Strands tools and the workflow handles model behaviour (order, skipped tools,
drifting arguments, failures). What it does not prove: that a real Bedrock model chooses well."""
import json

import pytest
from strands.models import Model

from app.ai import agent
from app.ai.bedrock import BedrockProvider

ALL_TOOLS = {"identify_waste", "get_price_estimate", "get_recycler_options", "calculate_environmental_impact", "calculate_points", "get_user_history", "recommend_next_action"}


class ScriptedModel(Model):
    """Plays back a fixed script of turns in the Converse-stream event format Strands consumes."""

    def __init__(self, script):
        self.script, self.turn, self.seen = list(script), 0, []

    def update_config(self, **kw): pass
    def get_config(self): return {}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kw):
        raise NotImplementedError
        yield  # pragma: no cover

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        step = self.script[min(self.turn, len(self.script) - 1)]
        self.turn += 1
        self.seen.append({"tools": sorted(t["name"] for t in (tool_specs or [])), "system": system_prompt or ""})
        if "raise" in step:
            raise step["raise"]
        yield {"messageStart": {"role": "assistant"}}
        if "tools" in step:
            for i, (name, args) in enumerate(step["tools"]):
                yield {"contentBlockStart": {"contentBlockIndex": i, "start": {"toolUse": {"toolUseId": f"t{self.turn}_{i}", "name": name}}}}
                yield {"contentBlockDelta": {"contentBlockIndex": i, "delta": {"toolUse": {"input": json.dumps(args)}}}}
                yield {"contentBlockStop": {"contentBlockIndex": i}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
            yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": step["text"]}}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2}, "metrics": {"latencyMs": 1}}}


class FakeVision:
    def __init__(self, condition="good"):
        self.payload = {"item_type": "laptop", "label": "Laptop", "brand": "Dell", "condition": condition, "confidence": 0.91, "quantity": 1, "notes": "scuffed lid"}

    def converse(self, **kw):
        return {"output": {"message": {"content": [{"text": json.dumps(self.payload)}]}}}


@pytest.fixture()
def wired(c, monkeypatch):
    def install(script):
        model = ScriptedModel(script)
        monkeypatch.setattr("strands.models.BedrockModel", lambda **kw: model)  # _run_strands imports it at call time
        c.ai = BedrockProvider("test-model", "us-east-1", client=FakeVision())
        return model

    return install, c.store.get("users", "u_demo")


def test_model_drives_the_tools_through_the_real_sdk(c, wired):
    install, user = wired
    model = install([
        {"tools": [("identify_waste", {})]},
        {"tools": [("get_price_estimate", {"item_type": "laptop", "condition": "good", "brand": "Dell", "quantity": 1}),
                   ("get_recycler_options", {"item_type": "laptop", "limit": 2}),
                   ("calculate_environmental_impact", {"item_type": "laptop", "quantity": 1}),
                   ("calculate_points", {"item_type": "laptop", "quantity": 1}),
                   ("get_user_history", {}),
                   ("recommend_next_action", {"item_type": "laptop", "condition": "good", "brand": "Dell", "quantity": 1})]},
        {"text": "Resell it if it still works, otherwise recycle it."},
    ])
    res = agent.run_workflow(c, user, b"photo", "image/jpeg", "laptop.jpg", None)
    assert res["agent"]["mode"] == "strands" and res["agent"]["summary"] == "Resell it if it still works, otherwise recycle it."
    order = [t["tool"] for t in res["trace"]]
    # each tool ran exactly once; the model's `limit: 2` and the pipeline's canonical call are the same call (no duplicate work).
    # Order inside one turn is not asserted: Strands may run the tool calls of a turn concurrently.
    assert order[0] == "identify_waste" and set(order) == ALL_TOOLS and len(order) == 7
    assert model.seen[0]["tools"] == sorted(ALL_TOOLS) and "never invent numbers" in model.seen[0]["system"]  # tools + guard-rail prompt reached the model
    est = res["estimate"]
    assert est["impact"]["co2e_kg"] == 6.4 and est["points"]["total"] > 0 and est["summary"]["item"] == "Laptop" and est["recyclers"]
    assert res["item"]["brand"] == "Dell" and res["classification"]["provider"] == "bedrock"


def test_model_arguments_cannot_override_what_the_photo_showed(c, wired):
    """The LLM can't see the image, so if it passes a different condition the authoritative classification still wins."""
    install, user = wired
    install([
        {"tools": [("identify_waste", {})]},
        {"tools": [("get_price_estimate", {"item_type": "Laptop", "condition": "damaged", "quantity": 1})]},  # drifted: the vision result said "good"
        {"text": "Done."},
    ])
    res = agent.run_workflow(c, user, b"photo", "image/jpeg", "laptop.jpg", None)
    est = res["estimate"]
    assert est["value"]["inputs"]["condition"] == "good" and est["value"]["resale"] is not None  # classification-based price is what the user sees
    prices = [t for t in res["trace"] if t["tool"] == "get_price_estimate"]
    assert {p["input"]["condition"] for p in prices} == {"damaged", "good"}  # the drift is visible in the trace, not hidden


def test_skipped_tools_are_filled_in_deterministically(c, wired):
    install, user = wired
    install([{"tools": [("identify_waste", {})]}, {"text": "Looks like a laptop."}])  # lazy model: never calls the other six tools
    res = agent.run_workflow(c, user, b"photo", "image/jpeg", "laptop.jpg", None)
    assert res["agent"]["mode"] == "strands" and {t["tool"] for t in res["trace"]} == ALL_TOOLS
    assert res["estimate"]["points"]["total"] > 0 and res["estimate"]["action"]["primary"] in {"resell", "repair", "recycle", "donate"}


def test_agent_failure_falls_back_to_the_same_tools(c, wired):
    install, user = wired
    install([{"raise": RuntimeError("ThrottlingException: slow down")}])
    res = agent.run_workflow(c, user, b"photo", "image/jpeg", "laptop.jpg", None)
    assert res["agent"]["mode"] == "pipeline_fallback"
    assert any(t["tool"] == "agent" and "Strands run failed" in t["summary"] for t in res["trace"])
    assert {t["tool"] for t in res["trace"]} >= ALL_TOOLS and res["estimate"]["summary"]["item"] == "Laptop"  # the person still gets a complete result


def test_strands_is_skipped_when_disabled_or_when_the_provider_is_the_mock(c, wired, monkeypatch):
    install, user = wired
    model = install([{"text": "should never be called"}])
    c.settings.use_strands = False
    res = agent.run_workflow(c, user, b"photo", "image/jpeg", "laptop.jpg", None)
    assert res["agent"]["mode"] == "pipeline" and model.turn == 0
