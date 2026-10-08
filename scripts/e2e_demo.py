#!/usr/bin/env python3
"""Runs the 3-minute demo story against a running API, prints what changed, exits 1 if any step fails.
Use it to warm up and rehearse before recording:

  python scripts/e2e_demo.py --base http://localhost:8000
  python scripts/e2e_demo.py --base https://<api-id>.execute-api.<region>.amazonaws.com --real-ops

--real-ops walks the pickup through the collector and admin accounts (no demo shortcut).

REHEARSING WITHOUT SPOILING THE RECORDING: this script changes the account it uses (points, tier, rank). Rehearse with a throwaway
resident so demo@reloop.app stays pristine for the video:
  python scripts/e2e_demo.py --base <ApiUrl> --register --email rehearsal@example.com --password 'Str0ng#Pass1' --staff-password '<DemoPassword>'
Each run uploads a slightly different copy of the photo (duplicate detection is global, so the identical photo would be held for review)."""
import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
FAILS: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  ok    " if ok else "  FAIL  ") + msg)
    if not ok:
        FAILS.append(msg)


def title(n: int, t: str) -> None:
    print(f"\n[{n}] {t}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--email", default="demo@reloop.app", help="resident account to run the story as")
    ap.add_argument("--password", default="ReLoop#Demo1", help="that resident's password")
    ap.add_argument("--staff-password", default="ReLoop#Demo1", help="password of the collector/admin demo accounts")
    ap.add_argument("--register", action="store_true", help="create the resident first (409 = already exists is fine)")
    ap.add_argument("--image", default=str(ROOT / "frontend/public/samples/laptop.jpg"))
    ap.add_argument("--exact-image", action="store_true", help="upload the file unchanged (re-runs will then be flagged as duplicates)")
    ap.add_argument("--real-ops", action="store_true")
    a = ap.parse_args()
    http = httpx.Client(base_url=a.base.rstrip("/"), timeout=60)

    def login(email, password=None):
        r = http.post("/auth/login", json={"email": email, "password": password or (a.password if email == a.email else a.staff_password)})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def photo() -> bytes:
        raw = Path(a.image).read_bytes()
        if a.exact_image:
            return raw
        import io, random
        from PIL import Image, ImageDraw  # a few random pixels: new file hash, same picture
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        d = ImageDraw.Draw(im)
        for _ in range(40):
            x, y = random.randrange(im.width), random.randrange(im.height)
            d.rectangle([x, y, x + 3, y + 3], fill=tuple(random.randrange(256) for _ in range(3)))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        return buf.getvalue()

    photo_bytes = None

    title(0, "What is running")
    st = http.get("/system/status").json()
    rt = st["runtime"]
    print(f"  {st['banner']}")
    print(f"  AI={rt['ai']} ({rt['model_id']}), agent={rt['agent']}, store={rt['store']}, storage={rt['storage']}, auth={rt['auth']}, lambda={rt['in_lambda']}")

    title(1, f"{a.email} opens ReLoop")
    if a.register:
        rr = http.post("/auth/register", json={"email": a.email, "password": a.password, "name": "Rehearsal Resident", "building_id": "b_hostel_a"})
        print(f"  register: {rr.status_code} ({'created' if rr.status_code == 201 else rr.json().get('error', {}).get('message', rr.text)})")
    h = login(a.email)
    d0 = http.get("/dashboard", headers=h).json()
    s0 = http.get("/org/summary", headers=h).json()["score"]["score"]
    print(f"  {d0['points']['total']} points ({d0['points']['tier']['name']}), rank {('#' + str(d0['rank']['position'])) if d0['rank']['position'] else 'not yet ranked'} of {d0['rank']['of']}, building score {s0}")
    print(f"  Next best action: {d0['next_best_action']['title']}")

    title(2, "Scan the old laptop")
    photo_bytes = photo()
    r = http.post("/waste/analyze", headers=h, files={"image": ("laptop.jpg", photo_bytes, "image/jpeg")}).json()
    sub = r["submission"]
    sm = sub["estimate"]["summary"]
    print(f"  {sm['item']}, {int(sm['confidence'] * 100)}% confidence, {sm['condition']}, value {sm['estimated_value_min']}-{sm['estimated_value_max']} INR, {sm['estimated_weight_kg']} kg, ~{sm['estimated_co2_avoidance_kg']} kg CO2e")
    print(f"  Recommended: {sm['recommended_action']}  [{sub['agent']['mode']} agent, {len(sub['trace'])} tool calls]")
    check(bool(sm["item"]) and sub["status"] == "analyzed", f"AI result appears and is awaiting confirmation ({sm['item']})")
    print(f"  Proof: provider={sub['aws']['ai_provider']} model={sub['aws']['model_id']} store={sub['aws']['store']} object={sub['aws']['object_key']} request={sub['aws']['lambda_request_id']}")

    title(3, "Correct to damaged, confirm (human in the loop)")
    c = http.post("/waste/confirm", headers=h, json={"submission_id": sub["id"], "corrections": {"condition": "damaged"}}).json()
    print(f"  Now recommended: {c['estimate']['action']['headline']}; recycling value {c['estimate']['value']['recycle']}")
    check(c["estimate"]["action"]["primary"] == "recycle" and c["status"] == "confirmed", "correction to damaged re-estimates and recommends recycling")

    title(4, "Find a recycler and schedule the pickup")
    rec = http.get("/recyclers?category=computing&service=recycle", headers=h).json()["items"][0]
    print(f"  Nearest: {rec['name']} ({rec['distance_km']} km, {rec['verification']['label']})")
    p = http.post("/pickups", headers=h, json={"submission_ids": [sub["id"]], "mode": "pickup", "address": {"line": "Room 214, Hostel Block A, SVNIT", "city": "Surat", "pincode": "395007"},
                                               "date": (date.today() + timedelta(days=1)).isoformat(), "slot": "11:00-13:00"})
    check(p.status_code == 201, f"pickup requested ({p.json().get('recycler_name', p.text)})")
    pid = p.json()["id"]

    title(5, "Verification" + (" by collector and admin" if a.real_ops else " (demo fast-forward)"))
    if a.real_ops:
        col, adm = login("collector@reloop.app"), login("admin@reloop.app")
        for who, status in ((col, "scheduled"), (col, "collector_assigned"), (col, "picked_up")):
            http.patch(f"/pickups/{pid}/status", headers=who, json={"status": status}).raise_for_status()
        done = http.patch(f"/pickups/{pid}/status", headers=col, json={"status": "verified", "verified_weight_kg": 1.7}).json()
        http.patch(f"/pickups/{pid}/status", headers=adm, json={"status": "recycled"}).raise_for_status()
    else:
        done = http.post(f"/pickups/{pid}/fast-forward", headers=h).json()
    rw = done["rewards"]
    print(f"  +{rw['points']} points, +{rw['kg']} kg diverted, ~{rw['co2e_kg']} kg CO2e avoided (estimate)")
    print(f"  rank #{rw['rank_before']} -> #{rw['rank_after']}, tier {rw['tier_before']} -> {rw['tier_after']}, building score {rw['building_score_before']} -> {rw['building_score_after']}")
    check(rw["points"] > 0 and (rw["rank_before"] is None or rw["rank_after"] <= rw["rank_before"]), "points awarded and rank improved (or first entry on the board)")
    check(rw["building_score_after"] > rw["building_score_before"], "building ReLoop Score moved")

    title(6, "Everything updates")
    d1 = http.get("/dashboard", headers=h).json()
    check(d1["points"]["total"] == d0["points"]["total"] + rw["points"], f"ledger-backed balance {d0['points']['total']} -> {d1['points']['total']}")
    if d0["challenge"] and d0["challenge"]["joined"]:
        ch0, ch1 = d0["challenge"]["progress"], d1["challenge"]["progress"]
        check(ch1 > ch0, f"challenge '{d1['challenge']['title']}' progress {ch0:g} -> {ch1:g}")
    else:
        print("  (resident has not joined a challenge, so none moved)")
    lb = http.get("/leaderboard/building", headers=h).json()
    print(f"  Building leaderboard: {lb['me']['message']}")
    imp = http.get("/impact", headers=h).json()
    print(f"  My impact this month: {imp['this_month']['items']} items, {imp['this_month']['kg']} kg, ~{imp['this_month']['co2e_kg']} kg CO2e")

    title(7, "Advisor (grounded in the data above)")
    for q in ("How can my building improve?", "I have 8 kg of e-waste. Should I schedule a pickup?"):
        ad = http.post("/advisor/chat", headers=h, json={"message": q}).json()
        print(f"  Q: {q}\n  verified facts: {len(ad['verified'])}; {ad['recommendation']['label']} ({ad['recommendation']['generated_by']}): {ad['recommendation']['text'][:200]}")
        check(len(ad["verified"]) > 0, f"advisor returned verified facts for '{q[:30]}...'")

    title(8, "Abuse protection")
    r = http.post("/waste/analyze", headers=h, files={"image": ("laptop.jpg", photo_bytes, "image/jpeg")})
    if r.status_code == 429:  # the submission cooldown (also an abuse control): wait it out, then retry
        wait = int(r.headers.get("Retry-After", 4)) + 1
        print(f"  Cooldown active ({r.json()['error']['message']}) - waiting {wait}s")
        time.sleep(wait)
        r = http.post("/waste/analyze", headers=h, files={"image": ("laptop.jpg", photo_bytes, "image/jpeg")})
    dup = r.json()
    fr = dup["submission"]["fraud"] if dup.get("submission") else {}
    print(f"  Re-uploading the same photo -> {fr.get('status')} {[f['code'] for f in fr.get('flags', [])]}")
    check(fr.get("status") == "pending_review", "duplicate photo is held for review")

    title(9, "Admin view")
    adm = login("admin@reloop.app")
    an = http.get("/admin/dashboard", headers=adm).json()["analytics"]
    print(f"  {an['total_submissions']} submissions, {an['verified_submissions']} verified, AI correct first time {an['ai_accuracy']['correct_first_attempt_pct']}%, open fraud flags {an['open_fraud_flags']}")
    check(an["open_fraud_flags"] >= 1, "fraud review queue has the flagged duplicate")

    print("\n" + ("ALL STEPS PASSED" if not FAILS else f"{len(FAILS)} STEP(S) FAILED"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
