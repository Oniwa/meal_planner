"""
verify_meal_plan.py — deterministic meal plan verifier

CLI:
    python scripts/verify_meal_plan.py <meal_plan_path> <nutrition_plan_path>
    Exit 0: all checks pass. Exit 1: failures found.

Module:
    from scripts.verify_meal_plan import verify_plan
    result = verify_plan(meal_plan_dict, nutrition_plan_dict)
"""

import json
import sys
from dataclasses import dataclass, field

SLOTS = ["breakfast", "lunch", "dinner", "afternoon_snack", "night_snack"]
MAIN_SLOTS = ["breakfast", "lunch", "dinner"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FATTY_FISH_NAMES = {"salmon", "sardines", "mackerel", "tuna", "herring", "trout"}


@dataclass
class CheckFailure:
    check: str
    message: str


@dataclass
class VerifyResult:
    passing_days: list
    failing_days: dict
    global_failures: list

    @property
    def all_pass(self):
        return not self.global_failures and not self.failing_days


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_meal_variety(nutrition_plan):
    mv = nutrition_plan.get("meal_variety", {})
    if isinstance(mv, str):
        return {slot: mv for slot in SLOTS}
    return mv


def _calorie_target(day, nutrition_plan):
    training_days = nutrition_plan.get("training_days") or []
    training_cal = nutrition_plan.get("training_day_calories")
    rest_cal = nutrition_plan.get("rest_day_calories")
    if day in training_days and training_cal is not None:
        return training_cal
    if rest_cal is not None:
        return rest_cal
    return nutrition_plan["daily_calories"]


def _macro_target(day, nutrition_plan, key):
    training_days = nutrition_plan.get("training_days") or []
    training_val = nutrition_plan.get(f"training_day_{key}")
    rest_val = nutrition_plan.get(f"rest_day_{key}")
    if day in training_days and training_val is not None:
        return training_val
    if rest_val is not None:
        return rest_val
    return nutrition_plan[key]


def _is_training_day(day, nutrition_plan):
    training_days = nutrition_plan.get("training_days") or []
    return day in training_days and nutrition_plan.get("training_day_calories") is not None


def _within_15pct(actual, target):
    return target * 0.85 <= actual <= target * 1.15


def _delta_message(actual, target, unit=""):
    lo, hi = target * 0.85, target * 1.15
    if actual < lo:
        return f"short by {lo - actual:.0f}{unit}"
    return f"over by {actual - hi:.0f}{unit}"


# ---------------------------------------------------------------------------
# Global checks
# ---------------------------------------------------------------------------

def _check_allergens(meal_plan, nutrition_plan):
    allergies = [a.lower() for a in nutrition_plan.get("allergies") or []]
    if not allergies:
        return []
    failures = []
    for day_str, day_meals in meal_plan["week_plan"].items():
        for slot_name, slot in day_meals.items():
            if not isinstance(slot, dict):
                continue
            for ing in slot.get("ingredients", []):
                ing_name = ing["name"].lower()
                for allergen in allergies:
                    if allergen in ing_name:
                        failures.append(CheckFailure(
                            "allergen_check",
                            f"Allergen '{allergen}' in {slot_name} day {day_str}: {ing['name']}",
                        ))
    return failures


def _check_disliked_foods(meal_plan, nutrition_plan):
    disliked = [d.lower() for d in nutrition_plan.get("disliked_foods") or []]
    if not disliked:
        return []
    failures = []
    for day_str, day_meals in meal_plan["week_plan"].items():
        for slot_name, slot in day_meals.items():
            if not isinstance(slot, dict):
                continue
            for ing in slot.get("ingredients", []):
                ing_name = ing["name"].lower()
                for food in disliked:
                    if food in ing_name:
                        failures.append(CheckFailure(
                            "disliked_foods",
                            f"Disliked food '{food}' in {slot_name} day {day_str}: {ing['name']}",
                        ))
    return failures


def _check_fatty_fish(meal_plan, nutrition_plan):
    if not nutrition_plan.get("cholesterol_focus"):
        return []
    target = nutrition_plan.get("omega3_sessions_per_week")
    if target is None:
        return []
    count = 0
    for day_meals in meal_plan["week_plan"].values():
        for slot in day_meals.values():
            if not isinstance(slot, dict):
                continue
            for ing in slot.get("ingredients", []):
                if any(fish in ing["name"].lower() for fish in FATTY_FISH_NAMES):
                    count += 1
                    break  # count once per meal slot
    if count < target:
        return [CheckFailure("fatty_fish_count", f"Found {count} fatty fish session(s), target ≥ {target}")]
    return []


def _check_batch_cook(meal_plan, nutrition_plan):
    if not nutrition_plan.get("meal_prep_friendly"):
        return []
    batch_summary = meal_plan.get("batch_cook_summary")
    if batch_summary is None:
        return []
    summary_items = {entry["item"] for entry in batch_summary}
    failures = []
    for day_str, day_meals in meal_plan["week_plan"].items():
        for slot_name, slot in day_meals.items():
            if not isinstance(slot, dict):
                continue
            if any(t in slot.get("tags", []) for t in ("meal-prep", "batch-cook")):
                for ing in slot.get("ingredients", []):
                    if ing["name"] not in summary_items:
                        failures.append(CheckFailure(
                            "batch_cook_coverage",
                            f"Missing from batch_cook_summary: {ing['name']} (day {day_str} {slot_name})",
                        ))
    return failures


def _check_variety_low_global(meal_plan, nutrition_plan):
    meal_variety = _get_meal_variety(nutrition_plan)
    week_plan = meal_plan["week_plan"]
    failures = []
    for slot in SLOTS:
        if meal_variety.get(slot) != "low":
            continue
        recipes = {
            week_plan[d].get(slot, {}).get("name", "")
            for d in week_plan
            if isinstance(week_plan[d].get(slot), dict)
        }
        recipes.discard("")
        if len(recipes) < 3:
            failures.append(CheckFailure(
                "variety_low",
                f"{slot}: only {len(recipes)} distinct recipe(s), need ≥3 (variety=low)",
            ))
    return failures


# ---------------------------------------------------------------------------
# Per-day checks
# ---------------------------------------------------------------------------

def _slots_in_day(day_meals):
    return [v for v in day_meals.values() if isinstance(v, dict) and "calories" in v]


def _check_macros(day, day_meals, meal_plan, nutrition_plan):
    slots = _slots_in_day(day_meals)
    actual_cal = sum(s["calories"] for s in slots)
    actual_protein = sum(s["protein_grams"] for s in slots)
    actual_carbs = sum(s["carbs_grams"] for s in slots)
    actual_fat = sum(s["fat_grams"] for s in slots)

    cal_target = _calorie_target(day, nutrition_plan)
    protein_target = _macro_target(day, nutrition_plan, "protein_grams")
    carbs_target = _macro_target(day, nutrition_plan, "carbs_grams")
    fat_target = _macro_target(day, nutrition_plan, "fat_grams")

    checks = [
        (actual_cal, cal_target, "calories", ""),
        (actual_protein, protein_target, "protein", "g"),
        (actual_carbs, carbs_target, "carbs", "g"),
        (actual_fat, fat_target, "fat", "g"),
    ]
    failures = []
    for actual, target, label, unit in checks:
        if not _within_15pct(actual, target):
            lo, hi = target * 0.85, target * 1.15
            failures.append(CheckFailure(
                label,
                f"got {actual:.0f}{unit}, target {target:.0f}±15% ({lo:.0f}–{hi:.0f}) — {_delta_message(actual, target, unit)}",
            ))
    return failures


def _check_summary_arithmetic(day_str, day_meals, meal_plan):
    summary = (meal_plan.get("daily_nutrition_summary") or {}).get(day_str)
    if not summary:
        return []
    slots = _slots_in_day(day_meals)
    actual_cal = sum(s["calories"] for s in slots)
    actual_protein = sum(s["protein_grams"] for s in slots)
    actual_carbs = sum(s["carbs_grams"] for s in slots)
    actual_fat = sum(s["fat_grams"] for s in slots)

    failures = []
    if abs(summary["calories"] - actual_cal) > 5:
        failures.append(CheckFailure(
            "summary_arithmetic",
            f"calories: summary {summary['calories']:.0f} vs computed {actual_cal:.0f}",
        ))
    for key, actual in [("protein_grams", actual_protein), ("carbs_grams", actual_carbs), ("fat_grams", actual_fat)]:
        if abs(summary[key] - actual) > 1:
            failures.append(CheckFailure(
                "summary_arithmetic",
                f"{key}: summary {summary[key]:.0f}g vs computed {actual:.0f}g",
            ))
    return failures


def _check_breakfast_protein_floor(day_meals, nutrition_plan):
    breakfast = day_meals.get("breakfast")
    if not isinstance(breakfast, dict):
        return []
    total_protein = nutrition_plan["protein_grams"]
    floor_g = total_protein * 0.25
    actual = breakfast["protein_grams"]
    if actual < floor_g:
        return [CheckFailure(
            "breakfast_protein_floor",
            f"breakfast protein {actual:.0f}g ({actual / total_protein * 100:.0f}% of {total_protein}g) — floor is {floor_g:.0f}g (25%)",
        )]
    return []


def _check_cook_times(day_meals, nutrition_plan):
    max_time = nutrition_plan["max_cook_time_minutes"]
    failures = []
    for slot_name, slot in day_meals.items():
        if not isinstance(slot, dict):
            continue
        total = slot.get("prep_time_minutes", 0) + slot.get("cook_time_minutes", 0)
        if total > max_time:
            failures.append(CheckFailure(
                "cook_time",
                f"{slot_name}: {total} min exceeds max {max_time} min",
            ))
    return failures


def _check_variety(day, meal_plan, nutrition_plan):
    meal_variety = _get_meal_variety(nutrition_plan)
    week_plan = meal_plan["week_plan"]
    failures = []

    for slot in SLOTS:
        level = meal_variety.get(slot, "medium")
        this_recipe = week_plan.get(str(day), {}).get(slot, {})
        if not isinstance(this_recipe, dict):
            continue
        this_name = this_recipe.get("name", "")
        if not this_name:
            continue

        if level == "none":
            if day == 0:
                continue
            canonical = week_plan.get("0", {}).get(slot, {})
            if not isinstance(canonical, dict):
                continue
            if this_name != canonical.get("name", ""):
                failures.append(CheckFailure(
                    "variety_none",
                    f"{slot}: day {day} has '{this_name}', expected '{canonical.get('name')}' (variety=none requires same recipe every day)",
                ))

        elif level == "medium":
            for prev_day in range(day):
                prev = week_plan.get(str(prev_day), {}).get(slot, {})
                if isinstance(prev, dict) and this_name == prev.get("name", ""):
                    failures.append(CheckFailure(
                        "variety_medium",
                        f"{slot}: '{this_name}' repeats on day {day} (also on day {prev_day}); no repeats allowed in slot",
                    ))
                    break

        elif level == "high":
            for prev_day in range(day):
                for prev_slot in SLOTS:
                    prev = week_plan.get(str(prev_day), {}).get(prev_slot, {})
                    if isinstance(prev, dict) and this_name == prev.get("name", ""):
                        failures.append(CheckFailure(
                            "variety_high",
                            f"{slot}: '{this_name}' on day {day} repeats from day {prev_day} {prev_slot}; no repeats anywhere",
                        ))
                        break

    return failures


def _check_consecutive_repeat(day, meal_plan, nutrition_plan):
    if day == 0:
        return []
    meal_variety = _get_meal_variety(nutrition_plan)
    week_plan = meal_plan["week_plan"]
    failures = []
    for slot in MAIN_SLOTS:
        if meal_variety.get(slot, "medium") == "none":
            continue
        this = week_plan.get(str(day), {}).get(slot, {})
        prev = week_plan.get(str(day - 1), {}).get(slot, {})
        if not isinstance(this, dict) or not isinstance(prev, dict):
            continue
        if this.get("name") and this.get("name") == prev.get("name"):
            failures.append(CheckFailure(
                "consecutive_repeat",
                f"{slot}: '{this['name']}' on both day {day - 1} and day {day}",
            ))
    return failures


def _check_saturated_fat(day_meals, nutrition_plan):
    limit = nutrition_plan.get("saturated_fat_limit_grams")
    if limit is None:
        return []
    total = 0.0
    for slot in day_meals.values():
        if not isinstance(slot, dict):
            continue
        sat = slot.get("saturated_fat_grams")
        if sat is None:
            return []  # missing field — skip gracefully
        total += sat
    if total > limit:
        return [CheckFailure("saturated_fat", f"{total:.0f}g > {limit}g limit")]
    return []


def _check_soluble_fiber(day_str, meal_plan, nutrition_plan):
    target = nutrition_plan.get("soluble_fiber_target_grams")
    if target is None:
        return []
    summary = (meal_plan.get("daily_nutrition_summary") or {}).get(day_str, {})
    fiber = summary.get("soluble_fiber_grams")
    if fiber is None:
        return []
    if fiber < target:
        return [CheckFailure("soluble_fiber", f"day {day_str}: {fiber}g < {target}g target")]
    return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def verify_plan(meal_plan, nutrition_plan):
    global_failures = []
    global_failures.extend(_check_allergens(meal_plan, nutrition_plan))
    global_failures.extend(_check_disliked_foods(meal_plan, nutrition_plan))
    global_failures.extend(_check_fatty_fish(meal_plan, nutrition_plan))
    global_failures.extend(_check_batch_cook(meal_plan, nutrition_plan))
    global_failures.extend(_check_variety_low_global(meal_plan, nutrition_plan))

    passing_days = []
    failing_days = {}

    for day_str in sorted(meal_plan["week_plan"].keys(), key=int):
        day = int(day_str)
        day_meals = meal_plan["week_plan"][day_str]
        day_failures = []

        day_failures.extend(_check_macros(day, day_meals, meal_plan, nutrition_plan))
        day_failures.extend(_check_summary_arithmetic(day_str, day_meals, meal_plan))
        day_failures.extend(_check_breakfast_protein_floor(day_meals, nutrition_plan))
        day_failures.extend(_check_cook_times(day_meals, nutrition_plan))
        day_failures.extend(_check_variety(day, meal_plan, nutrition_plan))
        day_failures.extend(_check_consecutive_repeat(day, meal_plan, nutrition_plan))
        day_failures.extend(_check_saturated_fat(day_meals, nutrition_plan))
        day_failures.extend(_check_soluble_fiber(day_str, meal_plan, nutrition_plan))

        if day_failures:
            failing_days[day] = day_failures
        else:
            passing_days.append(day)

    return VerifyResult(
        passing_days=passing_days,
        failing_days=failing_days,
        global_failures=global_failures,
    )


# ---------------------------------------------------------------------------
# CLI output
# ---------------------------------------------------------------------------

_BAR = "─" * 60


def _day_label(day, nutrition_plan):
    label = DAY_NAMES[day]
    if _is_training_day(day, nutrition_plan):
        return f"Day {day} ({label}) [TRAINING]"
    return f"Day {day} ({label})"


def _format_report(result, meal_plan, nutrition_plan):
    lines = ["", "VERIFICATION REPORT", _BAR]

    # Global checks
    lines.append("GLOBAL CHECKS")
    global_checks = ["allergen_check", "disliked_foods", "fatty_fish_count", "batch_cook_coverage", "variety_low"]
    global_check_labels = {
        "allergen_check": "Allergen check",
        "disliked_foods": "Disliked foods",
        "fatty_fish_count": "Fatty fish count",
        "batch_cook_coverage": "Batch cook coverage",
        "variety_low": "Variety (low slots)",
    }
    failing_global = {f.check for f in result.global_failures}
    for check in global_checks:
        status = "FAIL" if check in failing_global else "PASS"
        lines.append(f"  {global_check_labels[check]:<28} {status}")
    for f in result.global_failures:
        lines.append(f"    ! {f.message}")

    # Per-day
    lines.append("")
    lines.append("DAY-BY-DAY CHECKS")
    for day_str in sorted(meal_plan["week_plan"].keys(), key=int):
        day = int(day_str)
        label = _day_label(day, nutrition_plan)
        day_failures = result.failing_days.get(day, [])
        status = "PASS" if not day_failures else "FAIL"
        lines.append(f"  {label}: {status}")
        for f in day_failures:
            lines.append(f"    - [{f.check}] {f.message}")

    # Corrections
    if result.failing_days:
        lines.append("")
        lines.append("CORRECTIONS NEEDED")
        for day in sorted(result.failing_days.keys()):
            label = _day_label(day, nutrition_plan)
            lines.append(f"  {label}:")
            for f in result.failing_days[day]:
                lines.append(f"    - {f.message}")

    # Summary
    total_days = len(meal_plan["week_plan"])
    passing = len(result.passing_days)
    failing_day_list = sorted(result.failing_days.keys())
    lines.append("")
    lines.append("SUMMARY")
    lines.append(f"  Days passing all checks: {passing} of {total_days}")
    lines.append(f"  Global checks passing:   {len(global_checks) - len(failing_global)} of {len(global_checks)}")
    if failing_day_list:
        lines.append(f"  Days needing correction: {failing_day_list}")
    lines.append(_BAR)
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/verify_meal_plan.py <meal_plan_path> <nutrition_plan_path>")
        sys.exit(2)

    meal_plan_path, nutrition_plan_path = sys.argv[1], sys.argv[2]

    with open(meal_plan_path) as f:
        meal_plan = json.load(f)
    with open(nutrition_plan_path) as f:
        nutrition_plan = json.load(f)

    result = verify_plan(meal_plan, nutrition_plan)
    print(_format_report(result, meal_plan, nutrition_plan))
    sys.exit(0 if result.all_pass else 1)


if __name__ == "__main__":
    main()
