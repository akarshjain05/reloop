from app.services.actions import recommend_action
from app.services.catalog import scoring_cfg
from app.services.impact import compute_impact
from app.services.points import compute_points, tier_for
from app.services.pricing import CuratedPriceProvider


def test_verified_laptop_points_match_documented_formula():
    r = compute_points("laptop", verified=True)
    assert r["total"] == 180  # 126 base x 1.00 weight x 1.14 recovery = 143.64, +20% verified, +5% segregation
    labels = [b["label"] for b in r["breakdown"]]
    assert any("Verified" in x for x in labels) and any("segregation" in x for x in labels)


def test_unverified_is_lower_and_bonuses_scale_not_stack_by_splitting():
    assert compute_points("laptop")["total"] < compute_points("laptop", verified=True)["total"]
    one = compute_points("charger", 10, verified=True)["total"]
    split = 10 * compute_points("charger", 1, verified=True)["total"]
    assert abs(one - split) <= 10  # segregation bonus is a % of base, so splitting items can't farm it


def test_weight_factor_is_monotonic_and_capped():
    light = compute_points("laptop", 1, 0.9, verified=True)["total"]
    typical = compute_points("laptop", 1, 1.8, verified=True)["total"]
    heavy = compute_points("laptop", 1, 3.6, verified=True)["total"]
    absurd = compute_points("laptop", 1, 100, verified=True)["total"]
    assert light < typical < heavy and absurd <= int(126 * 2.0 * 1.14 * 1.25) + 1


def test_event_bonus_is_capped():
    base = compute_points("laptop", verified=True)["total"]
    assert compute_points("laptop", verified=True, active_challenges=1)["total"] > base
    assert compute_points("laptop", verified=True, active_challenges=10)["total"] == compute_points("laptop", verified=True, active_challenges=3)["total"]


def test_tiers_and_positive_next_tier():
    t = tier_for(742)
    assert t["name"] == "Contributor" and t["next_name"] == "Advocate" and t["points_to_next"] == 8
    assert tier_for(99999)["next_name"] is None


def test_impact_laptop_matches_configured_assumptions():
    r = compute_impact("laptop", verified=True)
    assert r["weight_kg"] == 1.8 and r["co2e_kg"] == 6.4 and r["diverted_kg"] == 1.8
    assert sum(r["materials_kg"].values()) <= r["weight_kg"]
    assert r["is_estimate"] and "Illustrative" in r["disclaimer"]
    assert compute_impact("laptop")["diverted_kg"] == 0.0  # nothing counts as diverted until verified


def test_impact_scales_with_quantity_and_weight():
    assert compute_impact("charger", 5)["weight_kg"] == 0.6
    assert compute_impact("laptop", 1, 3.6)["co2e_kg"] > compute_impact("laptop", 1, 1.8)["co2e_kg"]


def test_price_estimate_is_labelled_not_live_and_condition_aware():
    p = CuratedPriceProvider()
    good, damaged = p.estimate("laptop", "good"), p.estimate("laptop", "damaged")
    assert good["is_live"] is False and good["label"] == "Estimated local market range" and "guaranteed" in good["disclaimer"]
    assert good["resale"]["max"] > good["resale"]["min"] > 0
    assert damaged["resale"] is None and damaged["recycle"]["max"] >= damaged["recycle"]["min"] > 0
    assert p.estimate("laptop", "good", "apple")["resale"]["max"] > good["resale"]["max"]
    assert p.estimate("charger", "good", quantity=5)["recycle"]["max"] >= 5 * p.estimate("charger", "good")["recycle"]["max"] - 5


def test_actions_follow_functional_vs_damaged_story():
    p = CuratedPriceProvider()
    assert recommend_action("laptop", "good", p.estimate("laptop", "good"))["primary"] == "resell"
    assert recommend_action("laptop", "damaged", p.estimate("laptop", "damaged"))["primary"] == "recycle"
    assert recommend_action("power_bank", "like_new", p.estimate("power_bank", "like_new"))["primary"] == "recycle"  # hazardous: never resell/bin
    assert recommend_action("charger", "good", p.estimate("charger", "good"))["primary"] == "donate"  # low resale value


def test_scoring_config_has_documented_keys():
    cfg = scoring_cfg()
    assert cfg["points"]["max_daily_points"] > 0 and sum(cfg["reloop_score"]["weights"].values()) == 100
