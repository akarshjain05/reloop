"""ReLoop triage agent — seven tools, one workflow.

  identify_waste -> get_price_estimate -> get_recycler_options -> calculate_environmental_impact
  -> calculate_points -> get_user_history -> recommend_next_action

With Amazon Bedrock the tools are driven by a Strands Agents SDK agent (the model decides the order and
writes a short rationale). Without it (demo / fallback) the SAME tools run as a fixed pipeline. Either way
every number comes from a tool, never from free-form model text, and each call is recorded in a trace.

NOTE: no `from __future__ import annotations` here — Strands reads the real type hints of the tool functions.
"""
import time

from ..core.logging import log_event
from ..models import kinds as K
from ..services import recyclers as recycler_svc
from ..services.actions import recommend_action
from ..services.catalog import CONDITION_LABELS, category_label, category_of, item_info, normalize_condition, normalize_item_type
from ..services.challenges import active_bonus_count
from ..services.impact import compute_impact
from ..services.points import compute_points
from ..services.stats import Snapshot, dates_by_user, since_window, streak_weeks, totals
from .types import AIUnavailable

STRANDS_SYSTEM = (
    "You are ReLoop's e-waste triage agent. For every submission you MUST use your tools and never invent numbers.\n"
    "Workflow: 1) identify_waste 2) get_price_estimate 3) get_recycler_options 4) calculate_environmental_impact "
    "5) calculate_points 6) get_user_history 7) recommend_next_action.\n"
    "Pass the exact item_type, condition, brand and quantity returned by identify_waste to the other tools.\n"
    "When the tools are done, reply with at most two plain sentences telling the user what to do and why. "
    "Quote numbers only as returned by tools and call them estimates."
)


class ToolContext:
    """Holds the inputs of one submission, the audit trace, and a cache so repeated tool calls are free."""

    def __init__(self, c, user, image=None, content_type="image/jpeg", filename=None, hint=None, ai=None):
        self.c, self.user = c, user
        self.image, self.content_type, self.filename, self.hint = image, content_type, filename, hint
        self.ai = ai or c.ai
        self.trace: list = []
        self.state: dict = {}
        self.inputs: dict = {}
        self.tools: dict = {}

    def run(self, name, inputs, fn):
        if name in self.inputs and self.inputs[name] == inputs:
            return self.state[name]
        t0 = time.perf_counter()
        out = fn()
        self.state[name], self.inputs[name] = out, inputs
        self.trace.append({"tool": name, "input": inputs, "summary": _summary(name, out), "ms": int((time.perf_counter() - t0) * 1000)})
        return out

    def preset_classification(self, cls: dict, note: str):
        self.state["identify_waste"], self.inputs["identify_waste"] = cls, {}
        self.trace.append({"tool": "identify_waste", "input": {}, "summary": note, "ms": 0})


def _inr(v) -> str:
    return f"₹{int(v):,}"


def _summary(name, out) -> str:
    if name == "identify_waste":
        return f"{out['label']}, {int(out['confidence'] * 100)}% confidence, {CONDITION_LABELS.get(out['condition'], out['condition']).lower()}"
    if name == "get_price_estimate":
        bits = []
        if out.get("resale"):
            bits.append(f"resale {_inr(out['resale']['min'])} to {_inr(out['resale']['max'])}")
        bits.append(f"recycle {_inr(out['recycle']['min'])} to {_inr(out['recycle']['max'])}")
        return ", ".join(bits) + " (curated demo range)"
    if name == "get_recycler_options":
        o = out["options"]
        return f"{len(o)} options, nearest is {o[0]['name']} at {o[0]['distance_km']} km" if o else "no accepting recycler found nearby"
    if name == "calculate_environmental_impact":
        return f"{out['weight_kg']} kg material, about {out['co2e_kg']} kg CO₂e (illustrative estimate)"
    if name == "calculate_points":
        return f"{out['total']} points once a pickup or drop-off is verified"
    if name == "get_user_history":
        return f"{out['items_30d']} items and {out['kg_30d']} kg in the last 30 days, {out['pending_unscheduled']} waiting for disposal"
    if name == "recommend_next_action":
        return f"{out['primary']}: {out['headline']}"
    return ""


def item_from_analysis(a: dict) -> dict:
    key = normalize_item_type(a.get("item_type"))
    info = item_info(key)
    return {"item_type": key, "label": a.get("label") or info["label"], "category": info["category"], "sub_category": info["sub_category"],
            "brand": a.get("brand"), "condition": normalize_condition(a.get("condition")), "quantity": int(a.get("quantity") or 1),
            "weight_kg": None, "confidence": float(a.get("confidence") or 0), "source": "ai"}


def _norm_item(item_type, condition="good", brand="", quantity=1):
    return normalize_item_type(item_type), normalize_condition(condition), (brand or "").strip()[:40], max(1, int(quantity or 1))


def build_tools(ctx: ToolContext) -> dict:
    c, user = ctx.c, ctx.user

    def identify_waste() -> dict:
        """Identify the e-waste item in the photo the user just uploaded. Call this first. Takes no arguments and returns item_type, label, brand, condition, confidence and quantity."""
        def go():
            a = ctx.ai.analyze_item(ctx.image, ctx.content_type, ctx.filename, ctx.hint)
            return a.to_dict()
        return ctx.run("identify_waste", {}, go)

    def get_price_estimate(item_type: str, condition: str = "good", brand: str = "", quantity: int = 1) -> dict:
        """Estimate resale and recycling value in INR. Values are a curated demo range, not live market prices.

        Args:
            item_type: catalog key returned by identify_waste, for example laptop
            condition: one of like_new, good, fair, damaged
            brand: brand name if known, otherwise empty
            quantity: number of identical items
        """
        it, cond, br, qty = _norm_item(item_type, condition, brand, quantity)
        return ctx.run("get_price_estimate", {"item_type": it, "condition": cond, "brand": br, "quantity": qty},
                       lambda: c.prices.estimate(it, cond, br or None, qty))

    def get_recycler_options(item_type: str, limit: int = 3) -> dict:
        """Find the nearest recyclers or drop-off points that accept this kind of item, with distance and pickup availability.

        Args:
            item_type: catalog key returned by identify_waste
            limit: how many options to return (at least 3, at most 5)
        """
        it = normalize_item_type(item_type)
        lim = max(3, min(5, int(limit or 3)))  # never fewer than the 3 the result card shows, so the agent's call and the pipeline's are the same call

        def go():
            lat, lng = recycler_svc.user_location(c, user)
            rows = recycler_svc.nearby(c, lat, lng, category=category_of(it), service="recycle")[:lim]
            keep = ("id", "name", "address", "distance_km", "pickup_available", "min_pickup_kg", "processing_days", "rating", "verification", "lat", "lng", "directions_url", "data_label", "hours")
            return {"options": [{k: r[k] for k in keep} for r in rows]}
        return ctx.run("get_recycler_options", {"item_type": it, "limit": lim}, go)

    def calculate_environmental_impact(item_type: str, quantity: int = 1, weight_kg: float = 0.0) -> dict:
        """Estimate material diverted, CO2e avoided and recoverable materials using the configured impact factors (illustrative).

        Args:
            item_type: catalog key returned by identify_waste
            quantity: number of identical items
            weight_kg: weight of ONE item in kg, or 0 to use the typical weight
        """
        it, _, _, qty = _norm_item(item_type, quantity=quantity)
        w = float(weight_kg) if weight_kg else None
        return ctx.run("calculate_environmental_impact", {"item_type": it, "quantity": qty, "weight_kg": w or 0.0},
                       lambda: compute_impact(it, qty, w))

    def calculate_points(item_type: str, quantity: int = 1, weight_kg: float = 0.0) -> dict:
        """Project the ReLoop points this item earns once a pickup or drop-off is verified, with the formula breakdown.

        Args:
            item_type: catalog key returned by identify_waste
            quantity: number of identical items
            weight_kg: weight of ONE item in kg, or 0 to use the typical weight
        """
        it, _, _, qty = _norm_item(item_type, quantity=quantity)
        w = float(weight_kg) if weight_kg else None
        return ctx.run("calculate_points", {"item_type": it, "quantity": qty, "weight_kg": w or 0.0},
                       lambda: compute_points(it, qty, w, verified=True, active_challenges=active_bonus_count(c, user["id"], it, category_of(it))))

    def get_user_history() -> dict:
        """Get this user's recent verified activity and how many confirmed items are still waiting for disposal."""
        def go():
            snap = Snapshot(c)
            t = totals(snap, since_window()).get(user["id"], {"items": 0, "kg": 0.0, "points": 0})
            waiting = [s for s in snap.submissions if s["user_id"] == user["id"] and s["status"] == "confirmed"]
            cats: dict = {}
            for i in snap.impacts:
                if i["user_id"] == user["id"]:
                    cats[i["category"]] = cats.get(i["category"], 0) + i["quantity"]
            top = max(cats, key=cats.get) if cats else None
            return {"items_30d": t["items"], "kg_30d": round(t["kg"], 1), "points_30d": t["points"], "pending_unscheduled": sum(s["item"]["quantity"] for s in waiting),
                    "streak_weeks": streak_weeks(dates_by_user(snap).get(user["id"], [])), "top_category": category_label(top) if top else None}
        return ctx.run("get_user_history", {}, go)

    def recommend_next_action(item_type: str, condition: str = "good", brand: str = "", quantity: int = 1) -> dict:
        """Decide what the user should do with this item (resell, repair, recycle or donate) and the concrete next step.

        Args:
            item_type: catalog key returned by identify_waste
            condition: one of like_new, good, fair, damaged
            brand: brand name if known, otherwise empty
            quantity: number of identical items
        """
        it, cond, br, qty = _norm_item(item_type, condition, brand, quantity)

        def go():
            price = c.prices.estimate(it, cond, br or None, qty)
            act = recommend_action(it, cond, price)
            lat, lng = recycler_svc.user_location(c, user)
            near = recycler_svc.nearby(c, lat, lng, category=category_of(it), service="recycle")
            step = {"label": "Find a recycler", "route": "/recyclers", "detail": "No accepting recycler found nearby yet."}
            if near:
                best = next((r for r in near if r["pickup_available"]), near[0])
                step = {"label": "Schedule a pickup" if best["pickup_available"] else "Plan a drop-off", "route": "/pickup" if best["pickup_available"] else "/recyclers",
                        "detail": f"{best['name']} is {best['distance_km']} km away and accepts this item."}
            return {**act, "next_step": step}
        return ctx.run("recommend_next_action", {"item_type": it, "condition": cond, "brand": br, "quantity": qty}, go)

    tools = {f.__name__: f for f in (identify_waste, get_price_estimate, get_recycler_options, calculate_environmental_impact,
                                     calculate_points, get_user_history, recommend_next_action)}
    ctx.tools = tools
    return tools


def complete_estimate(ctx: ToolContext, item: dict) -> dict:
    """Runs (or reuses from the agent's own calls) every enrichment tool for the confirmed/identified item."""
    t = ctx.tools
    it, cond, brand, qty, w = item["item_type"], item["condition"], item.get("brand") or "", item.get("quantity", 1), item.get("weight_kg") or 0.0
    price = t["get_price_estimate"](it, cond, brand, qty)
    rec = t["get_recycler_options"](it, 3)
    impact = t["calculate_environmental_impact"](it, qty, w)
    points = t["calculate_points"](it, qty, w)
    hist = t["get_user_history"]()
    action = t["recommend_next_action"](it, cond, brand, qty)
    resale = price.get("resale")
    use_recycle = action["primary"] == "recycle" or not resale
    rng = price["recycle"] if use_recycle else resale
    summary = {
        "item": item["label"], "category": "E-Waste", "sub_category": item["sub_category"], "condition": CONDITION_LABELS[cond],
        "confidence": item.get("confidence", 0), "recommended_action": action["headline"],
        "estimated_value_min": rng["min"], "estimated_value_max": rng["max"], "value_basis": "recycle" if use_recycle else "resale",
        "estimated_weight_kg": impact["weight_kg"], "estimated_recovery_score": impact["recovery_score"],
        "estimated_co2_avoidance_kg": impact["co2e_kg"], "recommended_disposal": "Authorised e-waste recycler" if action["primary"] == "recycle" else "Reuse first, recycle if it fails",
        "points": points["total"], "is_estimate": True, "note": "AI estimate — confirm item and condition for a more accurate value.",
    }
    return {"summary": summary, "value": price, "impact": impact, "points": points, "recyclers": rec["options"], "action": action, "history": hist}


def rule_summary(item: dict, est: dict) -> str:
    a, p = est["action"], est["points"]["total"]
    return f"{item['label']} ({CONDITION_LABELS[item['condition']].lower()}). {a['reason']} Recycling it through a verified pickup or drop-off would earn about {p} points."


def strands_available() -> bool:
    try:
        import strands  # noqa: F401
        return True
    except Exception:
        return False


def _run_strands(c, ctx: ToolContext) -> str:
    from strands import Agent, tool
    from strands.models import BedrockModel

    model = BedrockModel(model_id=c.settings.bedrock_model_id, region_name=c.settings.bedrock_region, temperature=0.1, max_tokens=800)
    agent = Agent(model=model, tools=[tool(f) for f in ctx.tools.values()], system_prompt=STRANDS_SYSTEM, callback_handler=None)
    result = agent("A user just uploaded a photo of an electronic item for triage. Run the workflow now.")
    return str(result).strip()[:600]


def run_workflow(c, user, image, content_type, filename, hint, ai=None) -> dict:
    ctx = ToolContext(c, user, image, content_type, filename, hint, ai)
    build_tools(ctx)
    mode, summary = "pipeline", ""
    if c.settings.use_strands and ctx.ai.name == "bedrock" and ctx.ai.supports_chat and strands_available():
        try:
            summary, mode = _run_strands(c, ctx), "strands"
        except Exception as e:  # any agent/runtime failure -> same tools, fixed order
            log_event("agent_fallback", error=f"{type(e).__name__}: {str(e)[:160]}")
            ctx.trace.append({"tool": "agent", "input": {}, "summary": "Strands run failed; continued with the fixed tool pipeline", "ms": 0})
            mode = "pipeline_fallback"
    cls = ctx.tools["identify_waste"]()  # cached if the agent already called it; raises AIUnavailable if the model can't answer
    item = item_from_analysis(cls)
    if not cls.get("electronics", True):
        return {"classification": cls, "item": item, "estimate": None, "trace": ctx.trace, "agent": {"mode": mode, "summary": "", "tools": list(ctx.tools)}}
    est = complete_estimate(ctx, item)
    return {"classification": cls, "item": item, "estimate": est, "trace": ctx.trace,
            "agent": {"mode": mode, "summary": summary or rule_summary(item, est), "tools": list(ctx.tools)}}


def manual_workflow(c, user, hint: str | None) -> dict:
    """AI unavailable: the user picks the item; the same enrichment tools still run."""
    ctx = ToolContext(c, user, ai=None)
    build_tools(ctx)
    key = normalize_item_type(hint)
    cls = {"item_type": key, "label": item_info(key)["label"], "confidence": 0.0, "condition": "good", "brand": None, "quantity": 1,
           "notes": "Manual selection", "electronics": True, "provider": "manual", "model_id": "none", "latency_ms": 0}
    ctx.preset_classification(cls, "AI unavailable, waiting for the user to choose the item manually")
    item = item_from_analysis(cls)
    item["source"] = "manual"
    est = complete_estimate(ctx, item)
    return {"classification": cls, "item": item, "estimate": est, "trace": ctx.trace,
            "agent": {"mode": "manual", "summary": "AI analysis is temporarily unavailable. Choose the item and condition below.", "tools": list(ctx.tools)}}


def estimate_for_item(c, user, item: dict) -> dict:
    ctx = ToolContext(c, user, ai=None)
    build_tools(ctx)
    return complete_estimate(ctx, item)
