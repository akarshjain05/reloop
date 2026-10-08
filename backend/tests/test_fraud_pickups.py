import io
from datetime import date

import pytest
from PIL import Image

from app.core.config import Settings
from app.core.security import create_user_doc
from app.main import create_app
from app.models import kinds as K
from app.services import pickups
from app.services.catalog import scoring_cfg
from app.services.images import average_hash, hamming, prepare_image
from fastapi.testclient import TestClient
from conftest import auth, make_image, today, upload


def confirmed(client, h, name="laptop.jpg", seed=1, corrections=None, hint=None):
    sid = upload(client, h, name, seed, hint).json()["submission"]["id"]
    r = client.post("/waste/confirm", headers=h, json={"submission_id": sid, "corrections": corrections})
    assert r.status_code == 200, r.text
    return sid


def new_user(client, email, password="Str0ng#Passw0rd"):
    r = client.post("/auth/register", json={"email": email, "password": password, "name": "Test User", "building_id": "b_hostel_a"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


def schedule(client, h, ids, **kw):
    body = {"submission_ids": ids, "mode": "pickup", "address": {"line": "Room 12, Hostel A", "city": "Surat", "pincode": "395007"}, "date": today(), "slot": "09:00-11:00", **kw}
    return client.post("/pickups", headers=h, json=body)


# ---- duplicate detection / abuse protection --------------------------------------------------------------
def test_exact_duplicate_is_flagged_and_queued_for_review(client):
    h, admin = auth(client), auth(client, "admin@reloop.app")
    assert upload(client, h, "laptop.jpg", 5).json()["submission"]["fraud"]["status"] == "ok"
    dup = upload(client, h, "laptop.jpg", 5).json()["submission"]["fraud"]
    assert dup["status"] == "pending_review" and dup["flags"][0]["code"] == "DUPLICATE_EXACT"
    queue = client.get("/admin/fraud", headers=admin).json()
    assert any(f["status"] == "open" and "DUPLICATE_EXACT" in f["reasons"] for f in queue)


def test_near_duplicate_image_is_detected_by_perceptual_hash():
    base = Image.open(io.BytesIO(make_image(7))).convert("RGB")
    tweaked = base.copy()
    for x in range(10):
        for y in range(10):
            tweaked.putpixel((x, y), (255, 255, 255))
    assert hamming(average_hash(base), average_hash(tweaked)) <= scoring_cfg()["fraud"]["near_duplicate_hamming"]
    assert hamming(average_hash(base), average_hash(Image.open(io.BytesIO(make_image(8))).convert("RGB"))) > 0


def test_similar_image_gets_a_flag(client):
    h = auth(client)
    upload(client, h, "a.jpg", 7)
    im = Image.open(io.BytesIO(make_image(7))).convert("RGB")
    im.putpixel((3, 3), (0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    r = client.post("/waste/analyze", headers=h, files={"image": ("b.jpg", buf.getvalue(), "image/jpeg")}).json()["submission"]["fraud"]
    assert {f["code"] for f in r["flags"]} & {"DUPLICATE_SIMILAR", "DUPLICATE_EXACT"}


def test_submission_cooldown(settings):
    settings.submission_cooldown_seconds = 30
    cl = TestClient(create_app(settings))
    h = auth(cl)
    assert upload(cl, h, "x.jpg", 31).status_code == 200
    r = upload(cl, h, "y.jpg", 32)
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited" and int(r.headers["Retry-After"]) >= 1


def test_upload_validation_and_exif_stripping(client, settings):
    h = auth(client)
    assert client.post("/waste/analyze", headers=h, files={"image": ("x.jpg", b"not an image", "image/jpeg")}).json()["error"]["code"] == "unsupported_type"
    assert client.post("/waste/analyze", headers=h, files={"image": ("x.jpg", b"\xff\xd8\xff" + b"0" * 100, "image/jpeg")}).json()["error"]["code"] == "unreadable_image"
    client.app.state.c.settings.max_upload_mb = 1
    big = client.post("/waste/analyze", headers=h, files={"image": ("big.jpg", b"\xff\xd8\xff" + b"0" * 1_200_000, "image/jpeg")})
    assert big.status_code == 413
    im = Image.new("RGB", (50, 50), "red")
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (21.0, 10.0, 0.0)}  # GPS IFD
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    out = prepare_image(buf.getvalue(), 5)["jpeg"]
    assert not Image.open(io.BytesIO(out)).getexif()  # GPS metadata is removed before storage


def test_admin_can_approve_held_points(client, c):
    admin = auth(client, "admin@reloop.app")
    flag = next(f for f in client.get("/admin/fraud", headers=admin).json() if f["status"] == "open" and f["held_points"] > 0)
    r = client.post(f"/admin/fraud/{flag['id']}/resolve", headers=admin, json={"action": "approve", "note": "checked photos"})
    assert r.status_code == 200 and r.json()["released_points"] == flag["held_points"]
    assert client.post(f"/admin/fraud/{flag['id']}/resolve", headers=admin, json={"action": "reject"}).status_code == 409


def test_flagged_submission_holds_points_until_review(client):
    h, admin = auth(client), auth(client, "admin@reloop.app")
    upload(client, h, "laptop.jpg", 41)
    sid = confirmed(client, h, "laptop.jpg", 41)  # exact duplicate -> flagged
    pid = schedule(client, h, [sid]).json()["id"]
    before = client.get("/dashboard", headers=h).json()["points"]["total"]
    r = client.post(f"/pickups/{pid}/fast-forward", headers=h).json()
    assert r["rewards"]["points_held"] is True and r["rewards"]["points"] == 0
    dash = client.get("/dashboard", headers=h).json()["points"]
    assert dash["total"] == before and dash["pending_review"] >= 100  # visible as pending, not counted
    flag = next(f for f in client.get("/admin/fraud", headers=admin).json() if f["submission_id"] == sid)
    client.post(f"/admin/fraud/{flag['id']}/resolve", headers=admin, json={"action": "approve"})
    assert client.get("/dashboard", headers=h).json()["points"]["total"] > before


# ---- pickup lifecycle -------------------------------------------------------------------------------------
def test_transition_table():
    assert pickups.can_transition("pickup", "requested", "scheduled")
    assert not pickups.can_transition("pickup", "requested", "verified")
    assert not pickups.can_transition("pickup", "picked_up", "recycled")
    assert pickups.can_transition("dropoff", "requested", "verified") and not pickups.can_transition("dropoff", "requested", "picked_up")


def test_full_lifecycle_with_roles_points_impact_and_challenge(client):
    user, col, admin = auth(client), auth(client, "collector@reloop.app"), auth(client, "admin@reloop.app")
    sid = confirmed(client, user, "laptop.jpg", 51, {"condition": "damaged"})
    pid = schedule(client, user, [sid]).json()["id"]
    patch = lambda who, **b: client.patch(f"/pickups/{pid}/status", headers=who, json=b)
    assert patch(user, status="scheduled").status_code == 403  # residents can't move their own request
    assert patch(col, status="verified").status_code == 409  # can't skip steps
    for st in ("scheduled", "collector_assigned", "picked_up"):
        assert patch(col, status=st).status_code == 200
    ch_before = next(x for x in client.get("/challenges", headers=user).json() if x["id"] == "chl_ewaste_week")["progress"]
    pts_before = client.get("/dashboard", headers=user).json()["points"]["total"]
    r = patch(col, status="verified", verified_weight_kg=2.4)
    assert r.status_code == 200
    rw = r.json()["rewards"]
    assert rw["kg"] == 2.4 and rw["points"] > 150 and rw["rank_after"] <= rw["rank_before"] and rw["items"] == 1
    assert client.get("/dashboard", headers=user).json()["points"]["total"] == pts_before + rw["points"]  # ledger-backed balance
    ch_after = next(x for x in client.get("/challenges", headers=user).json() if x["id"] == "chl_ewaste_week")["progress"]
    assert ch_after == pytest.approx(ch_before + 2.4)
    assert patch(col, status="verified").status_code == 409  # no double awards
    assert patch(user, status="recycled").status_code == 403 and patch(admin, status="recycled").status_code == 200
    unread = client.get("/notifications", headers=user).json()
    assert any("points earned" in n["title"] for n in unread["items"])
    impact = client.get("/impact", headers=user).json()
    assert impact["this_month"]["weighed_by_collector"] >= 1


def test_collector_cannot_touch_another_collectors_pickup(client, c):
    user, col = auth(client), auth(client, "collector@reloop.app")
    sid = confirmed(client, user, "laptop.jpg", 61)
    pid = schedule(client, user, [sid]).json()["id"]
    for st in ("scheduled", "collector_assigned"):
        client.patch(f"/pickups/{pid}/status", headers=col, json={"status": st})
    other = create_user_doc(c, "other.collector@example.com", "Other", "COLLECTOR", "b_hostel_a")
    oh = {"Authorization": f"Bearer {c.auth._token(other)['access_token']}"}
    assert client.patch(f"/pickups/{pid}/status", headers=oh, json={"status": "picked_up"}).status_code == 403


def test_daily_points_cap_is_enforced(client, monkeypatch):
    monkeypatch.setitem(scoring_cfg()["points"], "max_daily_points", 100)
    h, _ = new_user(client, "farmer@example.com")
    ids = [confirmed(client, h, "desktop.jpg", 70 + i, hint="desktop") for i in range(2)]
    pid = schedule(client, h, ids, recycler_id="r_greenloop").json()["id"]
    rw = client.post(f"/pickups/{pid}/fast-forward", headers=h).json()["rewards"]
    assert rw["points"] == 100 and any(a["capped"] for a in rw["awards"])


def test_dropoff_flow_and_cancel_returns_items(client):
    h, col = auth(client), auth(client, "collector@reloop.app")
    sid = confirmed(client, h, "charger.jpg", 81)
    r = client.post("/pickups", headers=h, json={"submission_ids": [sid], "mode": "dropoff", "recycler_id": "r_campus_bin"})
    assert r.status_code == 201 and r.json()["drop_code"] and [s["status"] for s in r.json()["steps"]] == ["requested", "verified", "recycled"]
    pid = r.json()["id"]
    assert client.patch(f"/pickups/{pid}/status", headers=col, json={"status": "verified"}).json()["rewards"]["points"] > 0
    tiny = confirmed(client, h, "cable.jpg", 83)
    r = schedule(client, h, [tiny])
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_recycler"  # 0.08 kg is below every pickup minimum -> drop-off instead
    sid2 = confirmed(client, h, "monitor.jpg", 82)
    pid2 = schedule(client, h, [sid2]).json()["id"]
    assert client.patch(f"/pickups/{pid2}/status", headers=h, json={"status": "cancelled"}).status_code == 200
    assert schedule(client, h, [sid2]).status_code == 201  # item became available again


def test_pickup_validation(client):
    h = auth(client)
    sid = confirmed(client, h, "laptop.jpg", 91)
    assert client.post("/pickups", headers=h, json={"submission_ids": [sid], "mode": "pickup"}).json()["error"]["code"] == "missing_schedule"
    assert schedule(client, h, [sid], slot="03:00-04:00").json()["error"]["code"] == "bad_slot"
    assert schedule(client, h, [sid], date="2020-01-01").json()["error"]["code"] == "bad_date"
    unconfirmed = upload(client, h, "mouse.jpg", 92).json()["submission"]["id"]
    assert schedule(client, h, [unconfirmed]).json()["error"]["code"] == "item_not_available"
    assert schedule(client, h, ["sub_nope"]).status_code == 404


def test_fast_forward_is_disabled_outside_demo_mode(client, c):
    h = auth(client)
    sid = confirmed(client, h, "laptop.jpg", 95)
    pid = schedule(client, h, [sid]).json()["id"]
    c.settings.demo_mode = False
    assert client.post(f"/pickups/{pid}/fast-forward", headers=h).status_code == 403
