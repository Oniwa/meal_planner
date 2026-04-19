"""
Tests for scripts/verify_meal_plan.py

Base fixture: 7-day plan, 4 slots/day (no night_snack), macros that pass all checks.
  daily_calories=2000, protein=150g, carbs=200g, fat=67g
  Slot distribution (sums to targets):
    breakfast:       500 cal, 45p, 45c, 13f   (30% of protein — passes 25% floor)
    lunch:           500 cal, 38p, 55c, 14f
    dinner:          600 cal, 42p, 70c, 18f
    afternoon_snack: 400 cal, 25p, 30c, 22f
"""

import copy
import pytest
from scripts.verify_meal_plan import verify_plan, CheckFailure


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _slot(name, calories=500, protein=38, carbs=50, fat=14,
          prep=5, cook=15, tags=None, ingredients=None, sat_fat=None):
    slot = {
        "name": name,
        "calories": float(calories),
        "protein_grams": float(protein),
        "carbs_grams": float(carbs),
        "fat_grams": float(fat),
        "prep_time_minutes": prep,
        "cook_time_minutes": cook,
        "tags": tags or [],
        "ingredients": ingredients or [{"name": "chicken breast", "quantity": 5, "unit": "oz"}],
    }
    if sat_fat is not None:
        slot["saturated_fat_grams"] = float(sat_fat)
    return slot


def _base_day(day_idx):
    """One day with macros that pass all checks and unique recipe names per slot."""
    return {
        "breakfast": _slot(
            f"Eggs Day {day_idx}", calories=500, protein=45, carbs=45, fat=13,
            ingredients=[{"name": "eggs", "quantity": 3, "unit": "large"}],
        ),
        "lunch": _slot(
            f"Salad Day {day_idx}", calories=500, protein=38, carbs=55, fat=14,
            ingredients=[{"name": "chicken breast", "quantity": 5, "unit": "oz"}],
        ),
        "dinner": _slot(
            f"Chicken Day {day_idx}", calories=600, protein=42, carbs=70, fat=18,
            ingredients=[{"name": "brown rice", "quantity": 1, "unit": "cup"}],
        ),
        "afternoon_snack": _slot(
            f"Apple Day {day_idx}", calories=400, protein=25, carbs=30, fat=22,
            ingredients=[{"name": "apple", "quantity": 1, "unit": "medium"}],
        ),
    }


def base_nutrition_plan():
    return {
        "name": "test",
        "daily_calories": 2000,
        "protein_grams": 150,
        "carbs_grams": 200,
        "fat_grams": 67,
        "max_cook_time_minutes": 60,
        "meal_prep_friendly": False,
        "cholesterol_focus": False,
        "omega3_sessions_per_week": None,
        "saturated_fat_limit_grams": None,
        "soluble_fiber_target_grams": None,
        "training_days": [],
        "training_day_calories": None,
        "training_day_carbs_grams": None,
        "training_day_protein_grams": None,
        "training_day_fat_grams": None,
        "rest_day_calories": None,
        "rest_day_carbs_grams": None,
        "rest_day_protein_grams": None,
        "rest_day_fat_grams": None,
        "allergies": [],
        "disliked_foods": [],
        "meal_variety": {
            "breakfast": "medium",
            "lunch": "medium",
            "dinner": "medium",
            "afternoon_snack": "medium",
            "night_snack": "none",
        },
    }


def base_meal_plan():
    week = {str(i): _base_day(i) for i in range(7)}
    summary = {
        str(i): {"calories": 2000.0, "protein_grams": 150.0, "carbs_grams": 200.0, "fat_grams": 67.0}
        for i in range(7)
    }
    return {"name": "test", "week_plan": week, "daily_nutrition_summary": summary}


# ---------------------------------------------------------------------------
# Global — allergen check
# ---------------------------------------------------------------------------

def test_allergen_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["allergies"] = ["peanuts"]
    result = verify_plan(mp, np)
    assert not any(f.check == "allergen_check" for f in result.global_failures)


def test_allergen_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["allergies"] = ["eggs"]
    result = verify_plan(mp, np)
    assert any(f.check == "allergen_check" for f in result.global_failures)


def test_allergen_case_insensitive():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["allergies"] = ["Eggs"]
    result = verify_plan(mp, np)
    assert any(f.check == "allergen_check" for f in result.global_failures)


def test_allergen_empty_list_skipped():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    result = verify_plan(mp, np)
    assert not any(f.check == "allergen_check" for f in result.global_failures)


# ---------------------------------------------------------------------------
# Global — disliked foods
# ---------------------------------------------------------------------------

def test_disliked_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["disliked_foods"] = ["broccoli"]
    result = verify_plan(mp, np)
    assert not any(f.check == "disliked_foods" for f in result.global_failures)


def test_disliked_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["disliked_foods"] = ["chicken breast"]
    result = verify_plan(mp, np)
    assert any(f.check == "disliked_foods" for f in result.global_failures)


def test_disliked_substring_match():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["disliked_foods"] = ["chicken"]
    result = verify_plan(mp, np)
    assert any(f.check == "disliked_foods" for f in result.global_failures)


# ---------------------------------------------------------------------------
# Global — fatty fish count
# ---------------------------------------------------------------------------

def _salmon_slot(name):
    return _slot(name, ingredients=[{"name": "salmon fillet", "quantity": 6, "unit": "oz"}])


def test_fatty_fish_skipped_when_no_cholesterol_focus():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["cholesterol_focus"] = False
    np["omega3_sessions_per_week"] = 3
    result = verify_plan(mp, np)
    assert not any(f.check == "fatty_fish_count" for f in result.global_failures)


def test_fatty_fish_skipped_when_omega3_null():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["cholesterol_focus"] = True
    np["omega3_sessions_per_week"] = None
    result = verify_plan(mp, np)
    assert not any(f.check == "fatty_fish_count" for f in result.global_failures)


def test_fatty_fish_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["cholesterol_focus"] = True
    np["omega3_sessions_per_week"] = 3
    for i in [0, 2, 4]:
        mp["week_plan"][str(i)]["dinner"] = _salmon_slot(f"Salmon Day {i}")
    result = verify_plan(mp, np)
    assert not any(f.check == "fatty_fish_count" for f in result.global_failures)


def test_fatty_fish_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["cholesterol_focus"] = True
    np["omega3_sessions_per_week"] = 3
    mp["week_plan"]["0"]["dinner"] = _salmon_slot("Salmon Day 0")
    result = verify_plan(mp, np)
    failures = [f for f in result.global_failures if f.check == "fatty_fish_count"]
    assert failures
    assert "1" in failures[0].message  # found 1 session, target is 3


def test_fatty_fish_counted_once_per_meal():
    """Two salmon ingredients in one meal count as 1 session, not 2."""
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["cholesterol_focus"] = True
    np["omega3_sessions_per_week"] = 2
    double_salmon = _slot(
        "Double Salmon",
        ingredients=[
            {"name": "salmon fillet", "quantity": 4, "unit": "oz"},
            {"name": "salmon roe", "quantity": 1, "unit": "tbsp"},
        ],
    )
    mp["week_plan"]["0"]["dinner"] = double_salmon
    mp["week_plan"]["1"]["dinner"] = _salmon_slot("Salmon Day 1")
    result = verify_plan(mp, np)
    assert not any(f.check == "fatty_fish_count" for f in result.global_failures)


# ---------------------------------------------------------------------------
# Global — batch cook coverage
# ---------------------------------------------------------------------------

def test_batch_cook_skipped_when_not_meal_prep():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_prep_friendly"] = False
    result = verify_plan(mp, np)
    assert not any(f.check == "batch_cook_coverage" for f in result.global_failures)


def test_batch_cook_skipped_when_no_summary():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_prep_friendly"] = True
    # no batch_cook_summary key in mp
    result = verify_plan(mp, np)
    assert not any(f.check == "batch_cook_coverage" for f in result.global_failures)


def test_batch_cook_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_prep_friendly"] = True
    mp["week_plan"]["0"]["lunch"] = _slot(
        "Batch Chicken", tags=["batch-cook"],
        ingredients=[{"name": "chicken breast", "quantity": 5, "unit": "oz"}],
    )
    mp["batch_cook_summary"] = [{"item": "chicken breast", "instructions": "grill"}]
    result = verify_plan(mp, np)
    assert not any(f.check == "batch_cook_coverage" for f in result.global_failures)


def test_batch_cook_fail_missing_ingredient():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_prep_friendly"] = True
    mp["week_plan"]["0"]["lunch"] = _slot(
        "Batch Chicken", tags=["batch-cook"],
        ingredients=[{"name": "chicken breast", "quantity": 5, "unit": "oz"}],
    )
    mp["batch_cook_summary"] = [{"item": "brown rice", "instructions": "cook"}]
    result = verify_plan(mp, np)
    assert any(f.check == "batch_cook_coverage" for f in result.global_failures)


def test_batch_cook_meal_prep_tag_also_triggers():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_prep_friendly"] = True
    mp["week_plan"]["0"]["lunch"] = _slot(
        "Batch Chicken", tags=["meal-prep"],
        ingredients=[{"name": "chicken breast", "quantity": 5, "unit": "oz"}],
    )
    mp["batch_cook_summary"] = []
    result = verify_plan(mp, np)
    assert any(f.check == "batch_cook_coverage" for f in result.global_failures)


# ---------------------------------------------------------------------------
# Global — variety low
# ---------------------------------------------------------------------------

def test_variety_low_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["lunch"] = "low"
    # Days 0-6 have unique recipes → 7 distinct → ≥3 ✓
    result = verify_plan(mp, np)
    assert not any(f.check == "variety_low" for f in result.global_failures)


def test_variety_low_fail_fewer_than_3_distinct():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["lunch"] = "low"
    for i in range(7):
        mp["week_plan"][str(i)]["lunch"] = _slot("Same Salad")
    result = verify_plan(mp, np)
    assert any(f.check == "variety_low" for f in result.global_failures)


def test_variety_low_fail_exactly_2_distinct():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["lunch"] = "low"
    for i in range(7):
        name = "Salad A" if i < 4 else "Salad B"
        mp["week_plan"][str(i)]["lunch"] = _slot(name)
    result = verify_plan(mp, np)
    assert any(f.check == "variety_low" for f in result.global_failures)


def test_variety_low_pass_exactly_3_distinct():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["lunch"] = "low"
    names = ["Salad A", "Salad B", "Salad C", "Salad A", "Salad B", "Salad C", "Salad A"]
    for i, name in enumerate(names):
        mp["week_plan"][str(i)]["lunch"] = _slot(name)
    result = verify_plan(mp, np)
    assert not any(f.check == "variety_low" for f in result.global_failures)


# ---------------------------------------------------------------------------
# Per-day — macro checks
# ---------------------------------------------------------------------------

def test_day_calories_pass():
    result = verify_plan(base_meal_plan(), base_nutrition_plan())
    assert 0 in result.passing_days


def test_day_calories_fail_too_low():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["0"]["dinner"]["calories"] = 100.0  # pulls total way below 85%
    result = verify_plan(mp, np)
    assert 0 in result.failing_days
    assert any(f.check == "calories" for f in result.failing_days[0])


def test_day_calories_fail_too_high():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["0"]["dinner"]["calories"] = 2000.0  # pulls total above 115%
    result = verify_plan(mp, np)
    assert 0 in result.failing_days
    assert any(f.check == "calories" for f in result.failing_days[0])


def test_day_protein_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    for slot in mp["week_plan"]["0"].values():
        slot["protein_grams"] = 1.0
    result = verify_plan(mp, np)
    assert any(f.check == "protein" for f in result.failing_days.get(0, []))


def test_day_carbs_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    for slot in mp["week_plan"]["0"].values():
        slot["carbs_grams"] = 1.0
    result = verify_plan(mp, np)
    assert any(f.check == "carbs" for f in result.failing_days.get(0, []))


def test_day_fat_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    for slot in mp["week_plan"]["0"].values():
        slot["fat_grams"] = 1.0
    result = verify_plan(mp, np)
    assert any(f.check == "fat" for f in result.failing_days.get(0, []))


def test_training_day_uses_training_targets():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["training_days"] = [0]
    np["training_day_calories"] = 2400
    np["training_day_protein_grams"] = 150
    np["training_day_carbs_grams"] = 275
    np["training_day_fat_grams"] = 67
    # day 0 still has 2000 cal → should fail against 2400 target
    result = verify_plan(mp, np)
    assert any(f.check == "calories" for f in result.failing_days.get(0, []))


def test_rest_day_uses_rest_targets_when_not_training():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["training_days"] = [0]
    np["training_day_calories"] = 2400
    np["rest_day_calories"] = 1500  # 2000 actual vs 1500 target = 33% over → fail
    np["training_day_protein_grams"] = 150
    np["rest_day_protein_grams"] = 150
    np["training_day_carbs_grams"] = 275
    np["rest_day_carbs_grams"] = 175
    np["training_day_fat_grams"] = 67
    np["rest_day_fat_grams"] = 67
    # day 1 is a rest day (not in training_days), target=1500, actual=2000 → fail
    result = verify_plan(mp, np)
    assert any(f.check == "calories" for f in result.failing_days.get(1, []))


def test_missing_training_days_field_uses_daily_calories():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    del np["training_days"]
    np["training_day_calories"] = 2400
    # without training_days, all days should use daily_calories (2000) and pass
    result = verify_plan(mp, np)
    assert not any(f.check == "calories" for f in result.failing_days.get(0, []))


# ---------------------------------------------------------------------------
# Per-day — summary arithmetic
# ---------------------------------------------------------------------------

def test_summary_arithmetic_pass():
    result = verify_plan(base_meal_plan(), base_nutrition_plan())
    for day in range(7):
        assert not any(f.check == "summary_arithmetic" for f in result.failing_days.get(day, []))


def test_summary_arithmetic_fail_calories():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["daily_nutrition_summary"]["0"]["calories"] = 1900.0  # actual sum is 2000, diff=100 >5
    result = verify_plan(mp, np)
    assert any(f.check == "summary_arithmetic" for f in result.failing_days.get(0, []))


def test_summary_arithmetic_pass_within_5_kcal():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["daily_nutrition_summary"]["0"]["calories"] = 2004.0  # diff=4 ≤5
    result = verify_plan(mp, np)
    assert not any(f.check == "summary_arithmetic" for f in result.failing_days.get(0, []))


def test_summary_arithmetic_fail_macro():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["daily_nutrition_summary"]["0"]["protein_grams"] = 148.0  # diff=2 >1
    result = verify_plan(mp, np)
    assert any(f.check == "summary_arithmetic" for f in result.failing_days.get(0, []))


def test_summary_arithmetic_pass_within_1g_macro():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["daily_nutrition_summary"]["0"]["protein_grams"] = 150.5  # diff=0.5 ≤1
    result = verify_plan(mp, np)
    assert not any(f.check == "summary_arithmetic" for f in result.failing_days.get(0, []))


# ---------------------------------------------------------------------------
# Per-day — breakfast protein floor
# ---------------------------------------------------------------------------

def test_breakfast_protein_floor_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    # breakfast has 45g protein, target=150, floor=37.5g → 45 ≥ 37.5 ✓
    result = verify_plan(mp, np)
    assert not any(f.check == "breakfast_protein_floor" for f in result.failing_days.get(0, []))


def test_breakfast_protein_floor_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["0"]["breakfast"]["protein_grams"] = 10.0  # 10/150=6.7% < 25%
    result = verify_plan(mp, np)
    assert any(f.check == "breakfast_protein_floor" for f in result.failing_days.get(0, []))


def test_breakfast_protein_floor_exactly_25_pct_passes():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["0"]["breakfast"]["protein_grams"] = 37.5  # exactly 25% of 150
    result = verify_plan(mp, np)
    assert not any(f.check == "breakfast_protein_floor" for f in result.failing_days.get(0, []))


# ---------------------------------------------------------------------------
# Per-day — cook time
# ---------------------------------------------------------------------------

def test_cook_time_pass():
    result = verify_plan(base_meal_plan(), base_nutrition_plan())
    assert not any(f.check == "cook_time" for f in result.failing_days.get(0, []))


def test_cook_time_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["0"]["dinner"]["prep_time_minutes"] = 30
    mp["week_plan"]["0"]["dinner"]["cook_time_minutes"] = 40  # 70 min > 60 min limit
    result = verify_plan(mp, np)
    assert any(f.check == "cook_time" for f in result.failing_days.get(0, []))


def test_cook_time_exactly_at_limit_passes():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["0"]["dinner"]["prep_time_minutes"] = 20
    mp["week_plan"]["0"]["dinner"]["cook_time_minutes"] = 40  # 60 == limit
    result = verify_plan(mp, np)
    assert not any(f.check == "cook_time" for f in result.failing_days.get(0, []))


# ---------------------------------------------------------------------------
# Per-day — variety: none
# ---------------------------------------------------------------------------

def test_variety_none_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["breakfast"] = "none"
    for i in range(7):
        mp["week_plan"][str(i)]["breakfast"] = _slot("Same Eggs")
    result = verify_plan(mp, np)
    assert not any(f.check == "variety_none" for f in
                   [f for d in result.failing_days.values() for f in d])


def test_variety_none_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["breakfast"] = "none"
    for i in range(7):
        mp["week_plan"][str(i)]["breakfast"] = _slot("Same Eggs")
    mp["week_plan"]["3"]["breakfast"] = _slot("Different Eggs")
    result = verify_plan(mp, np)
    assert any(f.check == "variety_none" for f in result.failing_days.get(3, []))


def test_variety_none_day0_never_flagged():
    """Day 0 is the canonical reference for 'none' variety — it cannot fail this check."""
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["breakfast"] = "none"
    result = verify_plan(mp, np)
    assert not any(f.check == "variety_none" for f in result.failing_days.get(0, []))


# ---------------------------------------------------------------------------
# Per-day — variety: medium
# ---------------------------------------------------------------------------

def test_variety_medium_pass():
    # Base fixture already uses unique recipe names per slot per day
    result = verify_plan(base_meal_plan(), base_nutrition_plan())
    for day in range(7):
        assert not any(f.check == "variety_medium" for f in result.failing_days.get(day, []))


def test_variety_medium_fail_repeat_in_slot():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["3"]["lunch"] = _slot("Salad Day 0")  # same as day 0's lunch name
    result = verify_plan(mp, np)
    assert any(f.check == "variety_medium" for f in result.failing_days.get(3, []))


def test_variety_medium_repeat_in_different_slot_ok():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    # Same name in lunch day 3 as in dinner day 0 — medium only checks within the same slot
    mp["week_plan"]["3"]["lunch"] = _slot("Chicken Day 0")
    result = verify_plan(mp, np)
    assert not any(f.check == "variety_medium" for f in result.failing_days.get(3, []))


# ---------------------------------------------------------------------------
# Per-day — variety: high
# ---------------------------------------------------------------------------

def test_variety_high_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["dinner"] = "high"
    # Base fixture already has unique names per slot per day
    result = verify_plan(mp, np)
    assert not any(f.check == "variety_high" for f in
                   [f for d in result.failing_days.values() for f in d])


def test_variety_high_fail_repeat_across_slots():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["dinner"] = "high"
    # Give day 3 dinner the same name as day 0 lunch — crosses slots
    mp["week_plan"]["3"]["dinner"] = _slot("Salad Day 0")
    result = verify_plan(mp, np)
    assert any(f.check == "variety_high" for f in result.failing_days.get(3, []))


def test_variety_high_fail_repeat_in_same_slot():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["dinner"] = "high"
    mp["week_plan"]["4"]["dinner"] = _slot("Chicken Day 1")
    result = verify_plan(mp, np)
    assert any(f.check == "variety_high" for f in result.failing_days.get(4, []))


# ---------------------------------------------------------------------------
# Per-day — consecutive repeat
# ---------------------------------------------------------------------------

def test_consecutive_repeat_pass():
    # Base fixture has unique recipes on adjacent days
    result = verify_plan(base_meal_plan(), base_nutrition_plan())
    for day in range(1, 7):
        assert not any(f.check == "consecutive_repeat" for f in result.failing_days.get(day, []))


def test_consecutive_repeat_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["1"]["dinner"] = _slot("Chicken Day 0")  # same as day 0 dinner
    result = verify_plan(mp, np)
    assert any(f.check == "consecutive_repeat" for f in result.failing_days.get(1, []))


def test_consecutive_repeat_not_checked_for_day0():
    result = verify_plan(base_meal_plan(), base_nutrition_plan())
    assert not any(f.check == "consecutive_repeat" for f in result.failing_days.get(0, []))


def test_consecutive_repeat_skip_when_variety_none():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"]["breakfast"] = "none"
    for i in range(7):
        mp["week_plan"][str(i)]["breakfast"] = _slot("Same Eggs")
    result = verify_plan(mp, np)
    assert not any(f.check == "consecutive_repeat" for f in
                   [f for d in result.failing_days.values() for f in d
                    if f.check == "consecutive_repeat"])


def test_consecutive_repeat_snack_slots_exempt():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    for i in range(7):
        mp["week_plan"][str(i)]["afternoon_snack"] = _slot("Same Snack")
    result = verify_plan(mp, np)
    assert not any(f.check == "consecutive_repeat" for f in
                   [f for d in result.failing_days.values() for f in d])


# ---------------------------------------------------------------------------
# Per-day — saturated fat
# ---------------------------------------------------------------------------

def test_saturated_fat_skipped_when_null():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["saturated_fat_limit_grams"] = None
    result = verify_plan(mp, np)
    assert not any(f.check == "saturated_fat" for f in
                   [f for d in result.failing_days.values() for f in d])


def test_saturated_fat_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["saturated_fat_limit_grams"] = 20
    for slot in mp["week_plan"]["0"].values():
        slot["saturated_fat_grams"] = 4.0  # 4 slots × 4g = 16g < 20g limit
    result = verify_plan(mp, np)
    assert not any(f.check == "saturated_fat" for f in result.failing_days.get(0, []))


def test_saturated_fat_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["saturated_fat_limit_grams"] = 20
    for slot in mp["week_plan"]["0"].values():
        slot["saturated_fat_grams"] = 6.0  # 4 × 6 = 24g > 20g limit
    result = verify_plan(mp, np)
    assert any(f.check == "saturated_fat" for f in result.failing_days.get(0, []))


def test_saturated_fat_skipped_when_field_absent_from_slot():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["saturated_fat_limit_grams"] = 20
    # slots don't have saturated_fat_grams — skip gracefully
    result = verify_plan(mp, np)
    assert not any(f.check == "saturated_fat" for f in result.failing_days.get(0, []))


# ---------------------------------------------------------------------------
# Per-day — soluble fiber
# ---------------------------------------------------------------------------

def test_soluble_fiber_skipped_when_null_target():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["soluble_fiber_target_grams"] = None
    result = verify_plan(mp, np)
    assert not any(f.check == "soluble_fiber" for f in
                   [f for d in result.failing_days.values() for f in d])


def test_soluble_fiber_skipped_when_field_absent_from_summary():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["soluble_fiber_target_grams"] = 12
    # daily_nutrition_summary does not have soluble_fiber_grams — skip
    result = verify_plan(mp, np)
    assert not any(f.check == "soluble_fiber" for f in
                   [f for d in result.failing_days.values() for f in d])


def test_soluble_fiber_pass():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["soluble_fiber_target_grams"] = 12
    for i in range(7):
        mp["daily_nutrition_summary"][str(i)]["soluble_fiber_grams"] = 14.0
    result = verify_plan(mp, np)
    assert not any(f.check == "soluble_fiber" for f in
                   [f for d in result.failing_days.values() for f in d])


def test_soluble_fiber_fail():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["soluble_fiber_target_grams"] = 12
    mp["daily_nutrition_summary"]["0"]["soluble_fiber_grams"] = 8.0
    result = verify_plan(mp, np)
    assert any(f.check == "soluble_fiber" for f in result.failing_days.get(0, []))


# ---------------------------------------------------------------------------
# all_pass / exit behaviour
# ---------------------------------------------------------------------------

def test_all_pass_when_clean():
    result = verify_plan(base_meal_plan(), base_nutrition_plan())
    assert result.all_pass


def test_all_pass_false_on_global_failure():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["allergies"] = ["eggs"]
    result = verify_plan(mp, np)
    assert not result.all_pass


def test_all_pass_false_on_day_failure():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["0"]["dinner"]["calories"] = 10.0
    result = verify_plan(mp, np)
    assert not result.all_pass


def test_passing_days_excludes_failing_days():
    np = base_nutrition_plan()
    mp = base_meal_plan()
    mp["week_plan"]["2"]["dinner"]["calories"] = 10.0
    result = verify_plan(mp, np)
    assert 2 not in result.passing_days
    assert 2 in result.failing_days


def test_legacy_flat_meal_variety_handled():
    """Plans with old flat meal_variety string don't crash."""
    np = base_nutrition_plan()
    mp = base_meal_plan()
    np["meal_variety"] = "medium"
    result = verify_plan(mp, np)
    assert result.all_pass
