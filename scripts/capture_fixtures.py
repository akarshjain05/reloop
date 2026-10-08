"""Captures REAL API responses from the seeded backend (including the whole demo journey) into
frontend/src/test/fixtures.json. The frontend tests replay them, so pages are tested against genuine payloads.
Run from the repo root:  PYTHONPATH=backend python scripts/capture_fixtures.py"""
import io
import json
import logging
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "src" / "test" / "fixtures.json"
SAMPLE = ROOT / "frontend" / "public" / "samples" / "laptop.jpg"

app = create_app(Settings(app_env="test", local_data_dir="/tmp/reloop_fixture_data", submission_cooldown_seconds=0, demo_mode=True))
cl = TestClient(app)


def login(email):
    r = cl.post("/auth/login", json={"email": email, "password": "ReLoop#Demo1"}).json()
    return {"Authorization": f"Bearer {r['access_token']}"}, r["user"]


def grab(h, paths):
    return {p: cl.get(p, headers=h).json() for p in paths}


COMMON = ["/system/status", "/public/stats", "/public/buildings", "/notifications", "/waste/options", "/recyclers?service=recycle", "/pickups/slots"]
fx = {"demo": {}, "org": {}, "admin": {}, "flows": {}}

h, demo_user = login("demo@reloop.app")
fx["demo"].update(grab(h, COMMON + ["/dashboard", "/impact", "/leaderboard?period=month", "/leaderboard/campus?period=month", "/leaderboard/building?period=month", "/leaderboard/neighborhood?period=month",
                                      "/leaderboard?period=all", "/challenges", "/prices/catalog", "/org/summary", "/pickups", "/waste/history"]))
fx["flows"]["demo_user"] = demo_user
fx["flows"]["dashboard_before"] = fx["demo"]["/dashboard"]

# the demo journey: scan -> AI result -> correct to damaged -> schedule -> verify
files = {"image": ("laptop.jpg", SAMPLE.read_bytes(), "image/jpeg")}
fx["flows"]["analyze"] = cl.post("/waste/analyze", headers=h, files=files).json()
sid = fx["flows"]["analyze"]["submission"]["id"]
fx["flows"]["confirm_plain"] = cl.post("/waste/confirm", headers=h, json={"submission_id": sid}).json()
fx["flows"]["confirm_damaged"] = cl.post("/waste/confirm", headers=h, json={"submission_id": sid, "corrections": {"item_type": "laptop", "condition": "damaged"}}).json()
fx["demo"]["/waste/history"] = cl.get("/waste/history", headers=h).json()
fx["flows"]["advisor"] = cl.post("/advisor/chat", headers=h, json={"message": "How can my building improve?"}).json()
fx["demo"]["/dashboard_waiting"] = cl.get("/dashboard", headers=h).json()
body = {"submission_ids": [sid], "mode": "pickup", "address": {"line": "Room 214, Hostel Block A, SVNIT", "city": "Surat", "pincode": "395007"},
        "date": (date.today() + timedelta(days=1)).isoformat(), "slot": "11:00-13:00"}
fx["flows"]["pickup_created"] = cl.post("/pickups", headers=h, json=body).json()
fx["demo"]["/pickups"] = cl.get("/pickups", headers=h).json()
done = cl.post(f"/pickups/{fx['flows']['pickup_created']['id']}/fast-forward", headers=h).json()
fx["flows"]["pickup_verified"], fx["flows"]["rewards"] = done, done["rewards"]
fx["flows"]["dashboard_after"] = cl.get("/dashboard", headers=h).json()
bin_ = cl.post("/waste/bin-scan", headers=h, files={"image": ("mixed-bin.jpg", (ROOT / "frontend/public/samples/mixed-bin.jpg").read_bytes(), "image/jpeg")}).json()
fx["flows"]["bin_scan"] = bin_
fx["flows"]["bin_confirm"] = cl.post(f"/waste/bin-scan/{bin_['id']}/confirm", headers=h, json={"removed": ["e_waste", "hazardous"]}).json()

h, user = login("org@reloop.app")
fx["org"].update(grab(h, COMMON + ["/dashboard", "/org/summary?scope=org", "/challenges"]))
fx["flows"]["org_user"] = user

h, user = login("admin@reloop.app")
fx["admin"].update(grab(h, COMMON + ["/pickups", "/admin/dashboard", "/admin/fraud", "/admin/predictions", "/admin/users", "/admin/recyclers"]))
fx["flows"]["admin_user"] = user
h, user = login("collector@reloop.app")
fx["flows"]["collector_user"] = user
fx["flows"]["collector_pickups"] = cl.get("/pickups", headers=h).json()

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(fx, separators=(",", ":")))
r = fx["flows"]["rewards"]
print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
print("journey:", fx["flows"]["analyze"]["submission"]["item"]["label"], "->", fx["flows"]["confirm_damaged"]["estimate"]["action"]["primary"], "| rewards:", r["points"], "pts", r["tier_before"], "->", r["tier_after"], "| score", r["building_score_before"], "->", r["building_score_after"])
