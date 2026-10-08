import json
import logging

import pytest

from app.ai.types import AIProvider
from app.core.logging import JsonFormatter, log_event
from conftest import auth, make_image, upload
from test_fraud_pickups import confirmed, new_user, schedule


def test_auth_errors_are_generic_and_validation_is_friendly(client):
    r = client.post("/auth/login", json={"email": "demo@reloop.app", "password": "wrong"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "Incorrect email or password."
    assert client.post("/auth/login", json={"email": "nobody@reloop.app", "password": "wrong"}).json()["error"]["message"] == r.json()["error"]["message"]
    v = client.post("/auth/register", json={"email": "bad", "password": "short", "name": ""})
    assert v.status_code == 422 and v.json()["error"]["code"] == "invalid_request" and v.json()["error"]["fields"]
    assert client.get("/dashboard").status_code == 401 and client.get("/dashboard", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_register_then_use_the_app(client):
    h, u = new_user(client, "fresh.user@example.com")
    assert u["role"] == "USER" and client.get("/auth/me", headers=h).json()["email"] == "fresh.user@example.com"
    assert client.post("/auth/register", json={"email": "fresh.user@example.com", "password": "Str0ng#Passw0rd", "name": "Dup"}).status_code == 409
    d = client.get("/dashboard", headers=h).json()
    assert d["points"]["total"] == 0 and "first verified item" in d["rank"]["message"] and d["next_best_action"]["cta"]["route"]


def test_dashboard_has_the_story_numbers(client):
    d = client.get("/dashboard", headers=auth(client)).json()
    assert d["month"]["items"] == 27 and 7.5 <= d["month"]["kg"] <= 9.5 and d["points"]["tier"]["next_name"]
    assert d["next_best_action"]["title"] and d["next_best_action"]["cta"] and d["building"]["score"] > 0
    assert d["challenge"]["id"] == "chl_ewaste_week" and d["challenge"]["joined"] and "estimated" in d["impact_story"]


def test_recyclers_sorted_filtered_and_labelled(client):
    h = auth(client)
    j = client.get("/recyclers?category=power", headers=h).json()
    d = [r["distance_km"] for r in j["items"]]
    assert d == sorted(d) and j["items"] and all("power" in r["accepts"] for r in j["items"])
    assert j["data_label"] == "Demo data" and "fictional" in j["notice"] and j["items"][0]["directions_url"].startswith("https://www.google.com/maps/dir/")
    assert all(r["verification"]["status"] != "verified" for r in j["items"])  # nothing claims real authorisation
    assert all("recycle" in r["services"] for r in client.get("/recyclers?service=recycle", headers=h).json()["items"])
    assert {r["id"] for r in client.get("/recyclers?service=repair", headers=h).json()["items"]} == {"r_piplod_repair"}
    assert client.get("/recyclers/nope", headers=h).status_code == 404


def test_leaderboards_are_positive_and_scoped(client):
    h = auth(client)
    for path in ("/leaderboard", "/leaderboard/building", "/leaderboard/campus", "/leaderboard/neighborhood"):
        j = client.get(path, headers=h).json()
        assert j["entries"][0]["rank"] == 1 and j["me"]["message"] and "last place" not in j["me"]["message"].lower()
    g = client.get("/leaderboard", headers=h).json()
    assert "more points to reach" in g["me"]["message"] and any(e["is_me"] for e in g["entries"])
    assert all(e.get("org") is not None for e in client.get("/leaderboard/neighborhood", headers=h).json()["entries"])
    nh, _ = new_user(client, "newbie@example.com")
    assert "first verified item" in client.get("/leaderboard/building", headers=nh).json()["me"]["message"]


def test_exchange_catalog_is_labelled_as_estimates(client):
    j = client.get("/prices/catalog", headers=auth(client)).json()
    assert j["is_live"] is False and j["label"] == "Estimated local market range" and "guaranteed" in j["disclaimer"]
    mac = next(x for x in j["items"] if x["name"].startswith("MacBook Air"))
    assert (mac["resale"]["min"], mac["resale"]["max"]) == (28000, 36000) and mac["action"]["primary"] == "resell"
    damaged = next(x for x in j["items"] if x["condition"] == "damaged")
    assert damaged["resale"] is None and damaged["action"]["primary"] == "recycle"
    assert {x["action"]["primary"] for x in j["items"]} <= {"resell", "repair", "recycle", "donate"}


def test_correction_updates_estimate_and_feeds_ai_accuracy(client):
    h, admin = auth(client), auth(client, "admin@reloop.app")
    sid = upload(client, h, "laptop.jpg", 111).json()["submission"]["id"]
    r = client.post("/waste/confirm", headers=h, json={"submission_id": sid, "corrections": {"item_type": "monitor", "quantity": 2, "weight_kg": 4, "brand": "LG"}}).json()
    assert r["item"]["label"] == "Monitor" and r["estimate"]["impact"]["weight_kg"] == 8 and r["item"]["source"] == "user_corrected"
    assert r["estimate"]["summary"]["estimated_weight_kg"] == 8 and r["estimate"]["value"]["inputs"]["quantity"] == 2
    sid2 = upload(client, h, "mouse.jpg", 112).json()["submission"]["id"]
    assert client.post("/waste/confirm", headers=h, json={"submission_id": sid2}).json()["item"]["source"] == "user_confirmed"
    acc = client.get("/admin/dashboard", headers=admin).json()["analytics"]["ai_accuracy"]
    assert 0 < acc["corrected_pct"] < 100 and acc["correct_first_attempt_pct"] + acc["corrected_pct"] == 100
    preds = client.get("/admin/predictions", headers=admin).json()
    assert any(p["corrected"] and p["predicted"] == "laptop" and p["final"] == "monitor" for p in preds)
    assert client.post("/waste/confirm", headers=h, json={"submission_id": sid, "corrections": {"quantity": 0}}).status_code == 422


def test_history_detail_media_and_ownership(client):
    h = auth(client)
    sid = upload(client, h, "laptop.jpg", 121).json()["submission"]["id"]
    assert any(x["id"] == sid for x in client.get("/waste/history", headers=h).json())
    detail = client.get(f"/waste/{sid}", headers=h).json()
    assert detail["image_url"].startswith("/media/") and "sha256" not in detail["image"]
    assert client.get(detail["image_url"]).headers["content-type"] == "image/jpeg"
    other, _ = new_user(client, "snoop@example.com")
    assert client.get(f"/waste/{sid}", headers=other).status_code == 403
    assert client.post("/waste/confirm", headers=other, json={"submission_id": sid}).status_code == 403
    assert client.get("/media/../../etc/passwd").status_code in (404, 400)


class FakeLLM(AIProvider):
    name, model_id, supports_chat = "bedrock", "fake", True

    def __init__(self):
        self.system = ""

    def analyze_item(self, *a, **k): raise NotImplementedError
    def analyze_bin(self, *a, **k): raise NotImplementedError

    def chat(self, system, messages):
        self.system = system
        return "LLM says: schedule a pickup."


def test_advisor_is_grounded_in_app_data(client, c):
    h = auth(client)
    ask = lambda m: client.post("/advisor/chat", headers=h, json={"message": m}).json()
    cases = {
        "What should I do with this old laptop?": "what_to_do", "Where can I recycle a power bank?": "where_recycle",
        "I have 8 kg of e-waste. Should I schedule a pickup?": "pickup_decision", "How can my apartment improve its recycling score?": "building_improve",
        "How much have I diverted this month?": "my_impact", "Which category should we focus on next month?": "focus_category",
        "What should our college do to increase e-waste collection?": "college_plan",
    }
    for msg, intent in cases.items():
        r = ask(msg)
        assert r["intent"] == intent, (msg, r["intent"])
        assert r["recommendation"]["label"] == "AI-generated recommendation" and r["recommendation"]["generated_by"] == "rules" and r["disclaimer"]
        assert all(f["source"] and f["value"] for f in r["verified"])
    assert any("power" in f["label"].lower() or f["label"].startswith(("Vesu", "GreenLoop", "Tapi", "Adajan", "Sachin", "Green Campus")) for f in ask("Where can I recycle a power bank?")["verified"])
    imp = ask("How much have I diverted this month?")
    assert any(f["label"].startswith("Weight diverted") and "kg" in f["value"] for f in imp["verified"])
    assert "Small electronics" in ask("Which category should we focus on next month?")["recommendation"]["text"] or "small electronics" in ask("Which category should we focus on next month?")["recommendation"]["text"].lower()
    llm = FakeLLM()
    c.ai = llm
    r = ask("How can my building improve?")
    assert r["recommendation"]["generated_by"] == "bedrock" and r["recommendation"]["text"].startswith("LLM says") and "VERIFIED_FACTS" in llm.system and "Never invent" in llm.system
    assert r["verified"]  # verified facts stay deterministic even when an LLM writes the recommendation


def test_reloop_score_is_explained_not_decorative(client):
    h, org, admin = auth(client), auth(client, "org@reloop.app"), auth(client, "admin@reloop.app")
    s = client.get("/org/summary", headers=h).json()
    assert s["scope"] == "building" and sum(x["weight"] for x in s["score"]["components"]) == 100
    assert abs(sum(x["points"] for x in s["score"]["components"]) - s["score"]["score"]) < 0.3 and "ReLoop Score =" in s["score"]["formula"]
    assert all(x["detail"] for x in s["score"]["components"]) and s["gap"]["top_gap"]["category"] == "small_electronics" and s["gap"]["drive"]["est_items"] > 0
    o = client.get("/org/summary", headers=org).json()
    assert o["scope"] == "org" and len(o["top_buildings"]) >= 3 and [b["score"] for b in o["top_buildings"]] == sorted((b["score"] for b in o["top_buildings"]), reverse=True)
    assert len(o["trend"]) == 6 and o["top_contributors"]
    assert client.get("/org/summary?scope=building&scope_id=b_technova", headers=h).status_code == 403
    assert client.get("/org/summary?scope=building&scope_id=b_technova", headers=admin).status_code == 200


def test_verification_moves_the_building_score_and_next_best_action(client):
    h = auth(client)
    sid = confirmed(client, h, "laptop.jpg", 131, {"condition": "damaged"})
    assert client.get("/dashboard", headers=h).json()["next_best_action"]["rule"] == "waiting_items"
    pid = schedule(client, h, [sid]).json()["id"]
    rw = client.post(f"/pickups/{pid}/fast-forward", headers=h).json()["rewards"]
    assert rw["building_score_after"] > rw["building_score_before"] and rw["rank_after"] < rw["rank_before"] and rw["co2e_kg"] == 6.4
    assert rw["tier_before"] == "Advocate" and rw["tier_after"] == "Steward"  # the seeded demo user crosses a tier with the laptop
    assert client.get("/dashboard", headers=h).json()["next_best_action"]["rule"] != "waiting_items"


def test_scan_my_waste_loop(client):
    h = auth(client)
    r = client.post("/waste/bin-scan", headers=h, files={"image": ("mixed-bin.jpg", make_image(141), "image/jpeg")}).json()
    status = {x["key"]: x["status"] for x in r["categories"]}
    assert status["e_waste"] == "warn" and status["hazardous"] == "warn" and status["plastic"] == "ok" and "Remove the battery" in r["advice"]
    before = client.get("/org/summary", headers=h).json()["score"]["score"]
    ok = client.post(f"/waste/bin-scan/{r['id']}/confirm", headers=h, json={"removed": ["e_waste", "hazardous"]}).json()
    assert ok["points_awarded"] == 5 and ok["building_score_after"] >= before and ok["clean_ratio"] == 1.0
    assert client.post(f"/waste/bin-scan/{r['id']}/confirm", headers=h, json={}).status_code == 409
    again = client.post("/waste/bin-scan", headers=h, files={"image": ("mixed-bin.jpg", make_image(142), "image/jpeg")}).json()
    assert client.post(f"/waste/bin-scan/{again['id']}/confirm", headers=h, json={}).json()["points_awarded"] == 0  # once per day: no farming


def test_admin_surface_is_protected_and_exports_are_safe(client, c):
    user, col, admin = auth(client), auth(client, "collector@reloop.app"), auth(client, "admin@reloop.app")
    for path in ("/admin/dashboard", "/admin/users", "/admin/fraud", "/admin/audit", "/admin/export/users", "/admin/predictions"):
        assert client.get(path, headers=user).status_code == 403 and client.get(path, headers=col).status_code == 403 and client.get(path, headers=admin).status_code == 200
    u = c.store.get("users", "u_001")
    u["name"] = "=HYPERLINK(\"http://evil\",\"x\")"
    c.store.put("users", "u_001", u)
    csv_text = client.get("/admin/export/users", headers=admin).text
    assert "'=HYPERLINK" in csv_text and "\n=HYPERLINK" not in csv_text
    assert client.get("/admin/export/secrets", headers=admin).status_code == 400
    assert any(a["action"] == "export.csv" for a in client.get("/admin/audit", headers=admin).json())  # exports are audited
    r = client.post("/admin/points/adjust", headers=admin, json={"user_id": "u_demo", "points": 25, "reason": "volunteer drive"})
    assert r.status_code == 200 and client.post("/admin/points/adjust", headers=user, json={"user_id": "u_demo", "points": 99, "reason": "cheat"}).status_code == 403


def test_admin_manages_recyclers_and_challenges(client):
    admin, org = auth(client, "admin@reloop.app"), auth(client, "org@reloop.app")
    r = client.post("/admin/recyclers", headers=admin, json={"name": "Test Recycler", "address": "1 Test Road, Surat", "lat": 21.17, "lng": 72.83, "accepts": ["computing"], "pickup_available": True,
                                                              "verification_status": "unverified"})
    assert r.status_code == 201 and r.json()["demo"] is False
    p = client.patch(f"/admin/recyclers/{r.json()['id']}", headers=admin, json={"verification_status": "verified", "license_no": "TEST-123"}).json()
    assert p["verification"]["status"] == "verified" and p["verification"]["license_no"] == "TEST-123"
    assert client.post("/admin/recyclers", headers=admin, json={"name": "x"}).status_code == 400
    ch = client.post("/admin/challenges", headers=org, json={"title": "Cable Week", "metric": "items", "goal": 50, "reward_points": 300, "days": 7, "item_type": "cable"})
    assert ch.status_code == 201 and any(x["title"] == "Cable Week" for x in client.get("/challenges", headers=org).json())


def test_status_headers_cors_and_stats(client, c):
    st = client.get("/system/status").json()
    assert st["demo_mode"] and len(st["demo_accounts"]) == 4 and st["runtime"]["ai"] == "mock" and not st["on_aws"] and "no AWS calls" in st["banner"]
    c.settings.demo_mode = False
    assert client.get("/system/status").json()["demo_accounts"] == []
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173" and r.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in client.get("/health", headers={"Origin": "https://evil.example"}).headers
    s = client.get("/public/stats").json()
    assert s["is_demo"] and s["items"] > 100 and s["kg"] > 0
    assert client.get("/nope").json()["error"]["message"] == "That page doesn't exist."


def test_structured_logs_are_json_and_redact_secrets():
    logging.disable(logging.NOTSET)
    try:
        import io
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        h.setFormatter(JsonFormatter())
        lg = logging.getLogger("reloop")
        lg.addHandler(h)
        lg.setLevel(logging.INFO)
        log_event("waste_submission", user_id="u1", category="laptop", status="verified", password="hunter2", token="abc")
        row = json.loads(buf.getvalue())
        assert row["event"] == "waste_submission" and row["category"] == "laptop" and row["password"] == "[redacted]" and row["token"] == "[redacted]" and "hunter2" not in buf.getvalue()
        lg.removeHandler(h)
    finally:
        logging.disable(logging.CRITICAL)
