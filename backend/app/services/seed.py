"""Deterministic demo data: Indian context, INR/kg, every entity fictional and flagged demo=True.
Gives charts history, a live ops queue, a fraud review queue and three challenges. Run via app startup
(memory store) or `python scripts/seed_demo.py` (DynamoDB)."""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ..core.security import hash_password
from ..models import kinds as K
from ..repositories.base import new_id
from .actions import recommend_action
from .catalog import item_info
from .impact import compute_impact
from .points import compute_points
from .recyclers import seed_recyclers

FIRST = ["Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Krishna", "Ishaan", "Rohan", "Kabir", "Yash", "Dev", "Nikhil", "Harsh", "Om", "Pranav",
         "Ananya", "Diya", "Aadhya", "Saanvi", "Kavya", "Myra", "Riya", "Navya", "Ira", "Neha", "Priya", "Tanvi", "Isha", "Jiya", "Meera"]
LAST = ["Patel", "Shah", "Desai", "Mehta", "Joshi", "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Singh", "Kulkarni", "Bhatt",
        "Trivedi", "Parekh", "Modi", "Chauhan", "Rana", "Pandya"]

ORGS = [
    {"id": "org_svnit", "name": "SVNIT Green Campus (Demo)", "type": "college", "city": "Surat"},
    {"id": "org_sunrise", "name": "Sunrise Heights Society (Demo)", "type": "society", "city": "Surat"},
    {"id": "org_technova", "name": "TechNova Office Park (Demo)", "type": "office", "city": "Surat"},
]
# members = residents enrolled in ReLoop (participation is measured against this)
BUILDINGS = [
    {"id": "b_hostel_a", "org_id": "org_svnit", "name": "Hostel Block A", "neighborhood": "Ichchhanath", "members": 40, "lat": 21.1674, "lng": 72.7862, "users": 12, "act": 1.0},
    {"id": "b_hostel_b", "org_id": "org_svnit", "name": "Hostel Block B", "neighborhood": "Ichchhanath", "members": 30, "lat": 21.1668, "lng": 72.7871, "users": 10, "act": 1.2},
    {"id": "b_academic", "org_id": "org_svnit", "name": "Academic Block", "neighborhood": "Ichchhanath", "members": 40, "lat": 21.1650, "lng": 72.7840, "users": 9, "act": 0.8},
    {"id": "b_quarters", "org_id": "org_svnit", "name": "Faculty Quarters", "neighborhood": "Ichchhanath", "members": 20, "lat": 21.1641, "lng": 72.7895, "users": 5, "act": 0.9},
    {"id": "b_sunrise", "org_id": "org_sunrise", "name": "Sunrise Heights, Tower 1", "neighborhood": "Ichchhanath", "members": 28, "lat": 21.1698, "lng": 72.7905, "users": 8, "act": 1.3},
    {"id": "b_technova", "org_id": "org_technova", "name": "TechNova Office Park", "neighborhood": "Adajan", "members": 45, "lat": 21.1950, "lng": 72.7960, "users": 6, "act": 0.6},
]
TYPE_WEIGHTS = {"laptop": 6, "smartphone": 9, "charger": 10, "cable": 7, "earphones": 6, "keyboard": 3, "mouse": 3, "monitor": 1.5, "tablet": 2, "router": 2,
                "hard_drive": 2, "power_bank": 3, "battery": 2, "printer": 0.4, "television": 0.4, "desktop_pc": 0.4, "motherboard": 1}
SMALL = {"charger", "cable", "earphones"}
CONDITIONS = ["good", "fair", "damaged", "like_new"]
COND_W = [35, 25, 35, 5]
# Akarsh's last-30-days recipe: 27 verified items, mostly small electronics (kept deliberately diverse)
ACT_SCALE = 2.4
DEMO_MONTH = ["charger"] * 7 + ["cable"] * 6 + ["earphones"] * 5 + ["mouse"] * 3 + ["keyboard"] * 2 + ["router", "hard_drive", "smartphone", "monitor"]


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def quick_estimate(c, it: str, cond: str, brand, qty: int, w_item: float) -> dict:
    price = c.prices.estimate(it, cond, brand, qty)
    impact = compute_impact(it, qty, w_item)
    pts = compute_points(it, qty, w_item, verified=True)
    action = recommend_action(it, cond, price)
    info = item_info(it)
    rng = price["recycle"] if (action["primary"] == "recycle" or not price["resale"]) else price["resale"]
    return {"value": price, "impact": impact, "points": pts, "action": action, "recyclers": [], "history": {},
            "summary": {"item": info["label"], "category": "E-Waste", "sub_category": info["sub_category"], "condition": cond, "confidence": 0.9,
                        "recommended_action": action["headline"], "estimated_value_min": rng["min"], "estimated_value_max": rng["max"],
                        "estimated_weight_kg": impact["weight_kg"], "estimated_co2_avoidance_kg": impact["co2e_kg"], "points": pts["total"], "is_estimate": True}}


def seed_demo(c, force: bool = False) -> dict:
    if not force and not c.store.is_empty():
        return {"skipped": True}
    rnd = random.Random(42)
    now = datetime.now(timezone.utc)
    docs: list[tuple[str, str, dict]] = []
    users: dict[str, dict] = {}
    by_b = {b["id"]: b for b in BUILDINGS}

    def put(kind, doc, id_=None):
        docs.append((kind, id_ or doc["id"], doc))

    seed_recyclers(c)
    for o in ORGS:
        put(K.ORGS, {**o, "demo": True})
    for b in BUILDINGS:
        put(K.BUILDINGS, {k: v for k, v in b.items() if k not in ("users", "act")} | {"demo": True})

    pw = hash_password(c.settings.demo_password)

    def add_user(uid, email, name, role, bid, with_pw=False, created_days=200):
        b = by_b[bid]
        u = {"id": uid, "email": email, "name": name, "role": role, "org_id": b["org_id"], "building_id": bid, "demo": True, "created_at": _iso(now - timedelta(days=created_days))}
        if with_pw:
            u["password_hash"] = pw
        users[uid] = u
        put(K.USERS, u)
        put(K.EMAIL_IDX, {"user_id": uid}, id_=email)

    add_user("u_demo", "demo@reloop.app", "Akarsh", "USER", "b_hostel_a", True)
    add_user("u_admin", "admin@reloop.app", "Platform Admin", "ADMIN", "b_hostel_a", True)
    add_user("u_collector", "collector@reloop.app", "Ravi Collector", "COLLECTOR", "b_hostel_a", True)
    add_user("u_orgadmin", "org@reloop.app", "Meera Campus Admin", "ORGANIZATION_ADMIN", "b_academic", True)
    used_names = {"Akarsh"}
    regular: list[dict] = []
    n = 0
    for b in BUILDINGS:
        for _ in range(b["users"]):
            while True:
                name = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
                if name not in used_names:
                    used_names.add(name)
                    break
            n += 1
            uid = f"u_{n:03d}"
            add_user(uid, f"{name.lower().replace(' ', '.')}.{n}@demo.reloop.app", name, "USER", b["id"], created_days=rnd.randint(60, 200))
            users[uid]["_act"] = ACT_SCALE * b["act"] * rnd.choice([0, 0.4, 0.7, 1, 1, 1.4, 2, 3])
            regular.append(users[uid])

    def emit_verified(user: dict, events: list[tuple[datetime, str, str, int]]) -> None:
        groups: dict = defaultdict(list)
        for ev in events:
            groups[(ev[0].year, ev[0].month)].append(ev)
        for evs in groups.values():
            evs.sort(key=lambda e: e[0])
            last = evs[-1][0]
            age_days = (now - last).days
            status = "recycled" if age_days > 14 else "verified"
            pk_id = new_id("pck")
            sub_ids, items = [], []
            for dt, it, cond, qty in evs:
                info = item_info(it)
                w = round(info["average_weight_kg"] * rnd.uniform(0.75, 1.3), 3)
                item = {"item_type": it, "label": info["label"], "category": info["category"], "sub_category": info["sub_category"], "brand": None,
                        "condition": cond, "quantity": qty, "weight_kg": w, "confidence": round(rnd.uniform(0.78, 0.97), 2), "source": "user_confirmed"}
                est = quick_estimate(c, it, cond, None, qty, w)
                sid, prid = new_id("sub"), new_id("prd")
                corrected = rnd.random() < 0.13
                put(K.PREDICTIONS, {"id": prid, "submission_id": sid, "user_id": user["id"], "provider": "seed-demo", "model_id": "seed", "latency_ms": 0,
                                    "raw": {"item_type": it, "confidence": item["confidence"]}, "corrected": corrected,
                                    "correction": {"condition": rnd.choice([x for x in CONDITIONS if x != cond])} if corrected else None, "final": item,
                                    "created_at": _iso(dt), "confirmed": True})
                pts = compute_points(it, qty, w, verified=True)
                imp = compute_impact(it, qty, w, verified=True)
                put(K.SUBMISSIONS, {"id": sid, "user_id": user["id"], "user_name": user["name"], "building_id": user["building_id"], "org_id": user["org_id"],
                                    "created_at": _iso(dt), "status": status, "ai_status": "ok", "prediction_id": prid, "item": item, "estimate": est,
                                    "image": {"key": None}, "fraud": {"score": 0, "flags": [], "status": "ok"}, "agent": {"mode": "seed", "summary": "", "tools": []},
                                    "trace": [], "aws": {}, "pickup_id": pk_id, "verified_at": _iso(dt + timedelta(days=2)), "awarded_points": pts["total"], "points_status": "posted"})
                put(K.IMPACT, {"id": new_id("imp"), "user_id": user["id"], "building_id": user["building_id"], "org_id": user["org_id"], "submission_id": sid,
                               "pickup_id": pk_id, "created_at": _iso(dt + timedelta(days=2)), "status": "recycled" if status == "recycled" else "verified",
                               "item_type": it, "category": info["category"], "quantity": qty, "weight_kg": imp["weight_kg"], "co2e_kg": imp["co2e_kg"],
                               "materials_kg": imp["materials_kg"], "value_mid_inr": est["value"]["recycle_mid"], "weight_source": "estimated"})
                put(K.LEDGER, {"id": new_id("pts"), "user_id": user["id"], "points": pts["total"], "status": "posted", "reason": f"{info['label']} recycled through a verified pickup",
                               "ref_type": "submission", "ref_id": sid, "created_at": _iso(dt + timedelta(days=2)), "meta": {"breakdown": pts["breakdown"], "seeded": True}})
                sub_ids.append(sid)
                items.append({"submission_id": sid, "label": info["label"], "quantity": qty})
            b = by_b[user["building_id"]]
            put(K.PICKUPS, {"id": pk_id, "user_id": user["id"], "user_name": user["name"], "building_id": user["building_id"], "org_id": user["org_id"], "mode": "pickup",
                            "submission_ids": sub_ids, "items": items, "recycler_id": "r_greenloop", "recycler_name": "GreenLoop E-Waste Hub (Demo)",
                            "address": {"line": f"{b['name']}, SVNIT Campus, Ichchhanath", "city": "Surat", "pincode": "395007"}, "date": last.date().isoformat(),
                            "slot": "11:00-13:00", "status": status, "total_kg": 0, "estimated_points": 0, "collector_id": "u_collector", "collector_name": "Ravi Collector",
                            "drop_code": None, "created_at": _iso(last), "rewards": None,
                            "history": [{"status": s, "at": _iso(last + timedelta(hours=6 * i)), "by": "Seed"} for i, s in enumerate(["requested", "scheduled", "collector_assigned", "picked_up", "verified"] + (["recycled"] if status == "recycled" else []))]})

    def random_events(act: float, b_id: str, n_items: int | None = None, max_days: float = 175, min_days: float = 0.0):
        weights = {k: (v * (0.12 if (b_id == "b_hostel_a" and k in SMALL) else 1)) for k, v in TYPE_WEIGHTS.items()}
        out = []
        for _ in range(n_items if n_items is not None else round(act * 9)):
            dt = now - timedelta(days=min_days + (max_days - min_days) * (rnd.random() ** 1.7), hours=rnd.uniform(0, 20))
            it = rnd.choices(list(weights), list(weights.values()))[0]
            out.append((dt, it, rnd.choices(CONDITIONS, COND_W)[0], rnd.randint(1, 3) if it in SMALL else 1))
        return out

    for u in regular:
        emit_verified(u, random_events(u["_act"], u["building_id"]))
    demo = users["u_demo"]
    month_events = [(now - timedelta(days=rnd.uniform(0.6, 28), hours=rnd.uniform(0, 12)), it, rnd.choices(CONDITIONS, COND_W)[0], 1) for it in DEMO_MONTH]
    older = [(now - timedelta(days=d, hours=h), it, "damaged", 1) for (d, h, it) in
             [(38, 5, "laptop"), (57, 9, "smartphone"), (83, 3, "tablet"), (112, 7, "laptop"), (141, 2, "charger"), (166, 11, "cable")]]
    emit_verified(demo, month_events + older)
    for u in users.values():
        u.pop("_act", None)


    def emit_waiting(user: dict) -> None:
        it = rnd.choice(["laptop", "smartphone", "monitor", "tablet", "keyboard", "charger"])
        info, cond = item_info(it), rnd.choice(["fair", "damaged", "good"])
        w = round(info["average_weight_kg"] * rnd.uniform(0.8, 1.2), 3)
        item = {"item_type": it, "label": info["label"], "category": info["category"], "sub_category": info["sub_category"], "brand": None, "condition": cond,
                "quantity": 1, "weight_kg": w, "confidence": 0.9, "source": "user_confirmed"}
        dt = now - timedelta(days=rnd.uniform(1, 26))
        sid, prid = new_id("sub"), new_id("prd")
        put(K.PREDICTIONS, {"id": prid, "submission_id": sid, "user_id": user["id"], "provider": "seed-demo", "model_id": "seed", "latency_ms": 0, "raw": {"item_type": it},
                            "corrected": False, "correction": None, "final": item, "created_at": _iso(dt), "confirmed": True})
        put(K.SUBMISSIONS, {"id": sid, "user_id": user["id"], "user_name": user["name"], "building_id": user["building_id"], "org_id": user["org_id"], "created_at": _iso(dt),
                            "status": "confirmed", "ai_status": "ok", "prediction_id": prid, "item": item, "estimate": quick_estimate(c, it, cond, None, 1, w), "image": {"key": None},
                            "fraud": {"score": 0, "flags": [], "status": "ok"}, "agent": {"mode": "seed", "summary": "", "tools": []}, "trace": [], "aws": {}})

    for u in regular:
        if rnd.random() < (0.75 if u["building_id"] == "b_hostel_a" else 0.4):
            for _ in range(rnd.randint(3, 5) if u["building_id"] == "b_hostel_a" else rnd.randint(1, 2)):
                emit_waiting(u)

    # live ops queue (other users): requested x3, scheduled x2, collector assigned x2, picked up x2
    stages = ["requested"] * 3 + ["scheduled"] * 2 + ["collector_assigned"] * 2 + ["picked_up"] * 2
    hostel_a = [u for u in regular if u['building_id'] == 'b_hostel_a']
    queue_users = rnd.sample(hostel_a, 3) + rnd.sample([u for u in regular if u not in hostel_a], len(stages) - 3)
    for user, stage in zip(queue_users, stages):
        it = rnd.choice(["laptop", "smartphone", "monitor", "hard_drive", "tablet", "router"])
        cond, info = rnd.choice(["damaged", "fair"]), item_info(it)
        w = round(info["average_weight_kg"] * rnd.uniform(0.8, 1.2), 3)
        item = {"item_type": it, "label": info["label"], "category": info["category"], "sub_category": info["sub_category"], "brand": None, "condition": cond,
                "quantity": 1, "weight_kg": w, "confidence": 0.9, "source": "user_confirmed"}
        est = quick_estimate(c, it, cond, None, 1, w)
        sid, prid, pk_id = new_id("sub"), new_id("prd"), new_id("pck")
        dt = now - timedelta(hours=rnd.uniform(3, 60))
        put(K.PREDICTIONS, {"id": prid, "submission_id": sid, "user_id": user["id"], "provider": "seed-demo", "model_id": "seed", "latency_ms": 0, "raw": {"item_type": it},
                            "corrected": False, "correction": None, "final": item, "created_at": _iso(dt), "confirmed": True})
        put(K.SUBMISSIONS, {"id": sid, "user_id": user["id"], "user_name": user["name"], "building_id": user["building_id"], "org_id": user["org_id"], "created_at": _iso(dt),
                            "status": "pickup_requested", "ai_status": "ok", "prediction_id": prid, "item": item, "estimate": est, "image": {"key": None},
                            "fraud": {"score": 0, "flags": [], "status": "ok"}, "agent": {"mode": "seed", "summary": "", "tools": []}, "trace": [], "aws": {}, "pickup_id": pk_id})
        order = ["requested", "scheduled", "collector_assigned", "picked_up"]
        put(K.PICKUPS, {"id": pk_id, "user_id": user["id"], "user_name": user["name"], "building_id": user["building_id"], "org_id": user["org_id"], "mode": "pickup",
                        "submission_ids": [sid], "items": [{"submission_id": sid, "label": info["label"], "quantity": 1}], "recycler_id": "r_greenloop",
                        "recycler_name": "GreenLoop E-Waste Hub (Demo)", "address": {"line": f"{by_b[user['building_id']]['name']}, Surat", "city": "Surat", "pincode": "395007"},
                        "date": (now + timedelta(days=rnd.randint(0, 3))).date().isoformat(), "slot": rnd.choice(["09:00-11:00", "14:00-16:00", "16:00-18:00"]), "status": stage,
                        "total_kg": est["impact"]["weight_kg"], "estimated_points": est["points"]["total"], "drop_code": None, "created_at": _iso(dt), "rewards": None,
                        "collector_id": "u_collector" if stage in ("collector_assigned", "picked_up") else None,
                        "collector_name": "Ravi Collector" if stage in ("collector_assigned", "picked_up") else None,
                        "history": [{"status": s, "at": _iso(dt + timedelta(hours=i)), "by": "Seed"} for i, s in enumerate(order[: order.index(stage) + 1])]})

    # fraud review queue: one flagged-and-held award, one flagged submission awaiting review
    fu = rnd.choice(regular)
    for k, (status, reasons, score) in enumerate([("verified", ["DUPLICATE_EXACT"], 70), ("confirmed", ["DUPLICATE_SIMILAR", "HIGH_VELOCITY"], 75)]):
        it, info = "laptop", item_info("laptop")
        item = {"item_type": it, "label": info["label"], "category": info["category"], "sub_category": info["sub_category"], "brand": None, "condition": "good", "quantity": 1,
                "weight_kg": 1.8, "confidence": 0.93, "source": "ai"}
        est = quick_estimate(c, it, "good", None, 1, 1.8)
        sid, prid = new_id("sub"), new_id("prd")
        dt = now - timedelta(days=1 + k)
        put(K.PREDICTIONS, {"id": prid, "submission_id": sid, "user_id": fu["id"], "provider": "seed-demo", "model_id": "seed", "latency_ms": 0, "raw": {"item_type": it},
                            "corrected": False, "correction": None, "final": item, "created_at": _iso(dt), "confirmed": True})
        put(K.SUBMISSIONS, {"id": sid, "user_id": fu["id"], "user_name": fu["name"], "building_id": fu["building_id"], "org_id": fu["org_id"], "created_at": _iso(dt),
                            "status": status, "ai_status": "ok", "prediction_id": prid, "item": item, "estimate": est, "image": {"key": None},
                            "fraud": {"score": score, "flags": [{"code": r, "score": score, "detail": "Similar image previously submitted."} for r in reasons], "status": "pending_review"},
                            "agent": {"mode": "seed", "summary": "", "tools": []}, "trace": [], "aws": {}, "points_status": "held" if status == "verified" else None})
        put(K.FRAUD, {"id": new_id("flg"), "submission_id": sid, "user_id": fu["id"], "user_name": fu["name"], "score": score, "reasons": reasons,
                      "details": ["Similar image previously submitted."], "status": "open", "created_at": _iso(dt), "message": "Suspicious submission detected — pending verification."})
        if status == "verified":
            put(K.LEDGER, {"id": new_id("pts"), "user_id": fu["id"], "points": 120, "status": "held", "reason": "Laptop recycled through a verified pickup", "ref_type": "submission",
                           "ref_id": sid, "created_at": _iso(dt), "meta": {"seeded": True}})

    # bin checks (segregation quality)
    for b in BUILDINGS:
        base = 0.6 if b["id"] == "b_hostel_a" else 0.8
        for _ in range(rnd.randint(6, 10)):
            ub = rnd.choice([u for u in users.values() if u["building_id"] == b["id"]])
            ratio = 1.0 if rnd.random() < base else rnd.choice([0.5, 0.5, 0.0])
            put(K.BIN_SCANS, {"id": new_id("bin"), "user_id": ub["id"], "building_id": b["id"], "org_id": b["org_id"], "created_at": _iso(now - timedelta(days=rnd.uniform(0, 28))),
                              "categories": [], "advice": "", "provider": "seed-demo", "model_id": "seed", "confirmed": True, "clean_ratio": ratio, "duplicate": False, "points_awarded": 0})

    # challenges
    def challenge(id_, title, desc, metric, goal, progress, reward, scope, org, starts, ends, item_type=None, category=None, who=None, n_part=20):
        pool = who or list(users.values())
        chosen = rnd.sample([u for u in pool if u["role"] == "USER" and u["id"] != "u_demo"], min(n_part, len([u for u in pool if u["role"] == "USER"]) - 1))
        if id_ == "chl_ewaste_week":
            chosen = [demo] + chosen
        shares = [rnd.random() + 0.2 for _ in chosen]
        s = sum(shares)
        for u, sh in zip(chosen, shares):
            put(K.PARTICIPANTS, {"id": f"{id_}:{u['id']}", "challenge_id": id_, "user_id": u["id"], "joined_at": _iso(now - timedelta(days=starts)), "contribution": round(progress * sh / s, 2)})
        put(K.CHALLENGES, {"id": id_, "title": title, "description": desc, "metric": metric, "goal": goal, "progress": progress, "reward_points": reward, "item_type": item_type,
                           "category": category, "scope": scope, "org_id": org, "status": "active", "starts_at": _iso(now - timedelta(days=starts)),
                           "ends_at": _iso(now + timedelta(days=ends)), "participants": len(chosen), "created_by": "u_admin", "demo": True})

    svnit = [u for u in users.values() if u["org_id"] == "org_svnit"]
    challenge("chl_ewaste_week", "E-Waste Week", "Divert 500 kg of e-waste together. Every verified kilogram counts.", "kg", 500, 327, 5000, "global", None, 6, 8, n_part=24)
    challenge("chl_chargers", "100 Chargers Challenge", "Collect 100 old chargers and adapters from across campus.", "items", 100, 62, 1500, "org", "org_svnit", 10, 20, item_type="charger", who=svnit, n_part=15)
    challenge("chl_cleanup", "Campus Cleanup", "1,000 electronic items responsibly processed on campus.", "items", 1000, 412, 3000, "org", "org_svnit", 20, 40, who=svnit, n_part=20)

    for title, body, ago in [("Pickup confirmed", "GreenLoop E-Waste Hub (Demo) confirmed your slot.", 3.2), ("+58 ReLoop points earned", "Verified recycling action.", 2.1),
                             ("E-Waste Week reached 50%", "250 of 500 kg so far.", 1.0)]:
        put(K.NOTIFS, {"id": new_id("ntf"), "user_id": "u_demo", "type": "seed", "title": title, "body": body, "created_at": _iso(now - timedelta(days=ago)), "read": False, "meta": {}})

    c.store.put_many(docs)
    return {"skipped": False, "documents": len(docs), "users": len(users), "buildings": len(BUILDINGS)}
