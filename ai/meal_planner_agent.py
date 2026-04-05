import json
import re
from collections import defaultdict
from pathlib import Path

from django.db import transaction

AGENT_MD_PATH = (
    Path(__file__).resolve().parent.parent / ".claude" / "agents" / "meal_planner_agent.md"
)

try:
    _SYSTEM_PROMPT = AGENT_MD_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    _SYSTEM_PROMPT = "You are an expert meal prep chef and nutritionist."

MEAL_SLOTS = ["breakfast", "lunch", "dinner", "afternoon_snack", "night_snack"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TOLERANCE = 0.15  # ±15%


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from a response string."""
    text = text.strip()
    pattern = r"^```(?:json)?\s*([\s\S]*?)\s*```$"
    match = re.match(pattern, text)
    if match:
        return match.group(1).strip()
    return text


def _validate_nutrition(parsed: dict, nutrition_plan) -> list[str]:
    """
    Check per-day totals against NutritionPlan targets within ±15%.
    Returns a list of error strings (empty if all pass).
    """
    targets = {
        "calories": nutrition_plan.daily_calories,
        "protein": nutrition_plan.protein_grams,
        "carbs": nutrition_plan.carbs_grams,
        "fat": nutrition_plan.fat_grams,
    }

    summary = parsed.get("daily_nutrition_summary", {})
    errors = []

    for day_key in [str(i) for i in range(7)]:
        day_data = summary.get(day_key)
        if not day_data:
            continue

        day_name = DAY_NAMES[int(day_key)]
        field_map = {
            "calories": day_data.get("calories", 0),
            "protein": day_data.get("protein_grams", 0),
            "carbs": day_data.get("carbs_grams", 0),
            "fat": day_data.get("fat_grams", 0),
        }

        for field, actual in field_map.items():
            target = targets[field]
            low = target * (1 - TOLERANCE)
            high = target * (1 + TOLERANCE)
            if not (low <= actual <= high):
                errors.append(
                    f"{day_name} {field}: got {actual},"
                    f" expected {target} ±15% ({low:.0f}–{high:.0f})"
                )

    return errors


def _build_user_message(nutrition_plan) -> str:
    """Build user message from a NutritionPlan instance."""
    plan_data = {
        "label": nutrition_plan.label,
        "daily_calories": nutrition_plan.daily_calories,
        "protein_grams": nutrition_plan.protein_grams,
        "carbs_grams": nutrition_plan.carbs_grams,
        "fat_grams": nutrition_plan.fat_grams,
        "heart_healthy": nutrition_plan.heart_healthy,
        "low_sodium": nutrition_plan.low_sodium,
        "low_sugar": nutrition_plan.low_sugar,
        "diabetic_friendly": nutrition_plan.diabetic_friendly,
        "anti_inflammatory": nutrition_plan.anti_inflammatory,
        "is_vegetarian": nutrition_plan.is_vegetarian,
        "is_vegan": nutrition_plan.is_vegan,
        "is_gluten_free": nutrition_plan.is_gluten_free,
        "is_dairy_free": nutrition_plan.is_dairy_free,
        "allergies": nutrition_plan.allergies,
        "disliked_foods": nutrition_plan.disliked_foods,
        "liked_foods": nutrition_plan.liked_foods,
        "preferred_cuisines": nutrition_plan.preferred_cuisines,
        "max_cook_time_minutes": nutrition_plan.max_cook_time_minutes,
        "meal_prep_friendly": nutrition_plan.meal_prep_friendly,
        "cooking_skill_level": nutrition_plan.cooking_skill_level,
        "meal_variety": nutrition_plan.meal_variety,
        "include_night_snack": nutrition_plan.include_night_snack,
    }

    if nutrition_plan.notes:
        plan_data["notes"] = nutrition_plan.notes

    message = f"""Generate a complete 7-day meal plan for the following nutrition plan:

{json.dumps(plan_data, indent=2)}

IMPORTANT: Set servings: 1 on all recipes. Ingredient quantities should be for exactly 1 serving.

Respond with pure JSON only (no markdown, no explanation) matching this schema:
{{
  "week_plan": {{
    "0": {{
      "breakfast": {{
        "name": "...",
        "description": "...",
        "instructions": "...",
        "prep_time_minutes": 0,
        "cook_time_minutes": 0,
        "servings": 1,
        "meal_type": "breakfast",
        "cuisine_type": "...",
        "calories": 0,
        "protein_grams": 0.0,
        "carbs_grams": 0.0,
        "fat_grams": 0.0,
        "fiber_grams": 0.0,
        "sodium_mg": 0.0,
        "tags": [],
        "ingredients": [
          {{"name": "...", "quantity": 0.0, "unit": "...", "category": "...",
           "notes": "optional note"}}
        ]
      }},
      "lunch": {{}},
      "dinner": {{}},
      "afternoon_snack": {{}}
    }}
  }},
  "daily_nutrition_summary": {{
    "0": {{"calories": 0, "protein_grams": 0.0, "carbs_grams": 0.0, "fat_grams": 0.0}}
  }}
}}

Day keys are "0" through "6" (0=Monday, 6=Sunday).
Include "night_snack" in each day only if include_night_snack is true.
"""
    return message


def _call_api(client, messages: list[dict]) -> str:
    """Call the Anthropic API with a 120s timeout and return the text content."""
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        messages=messages,
        timeout=120,
    )
    return response.content[0].text


def _parse_response(text: str) -> dict:
    """Strip fences and parse JSON, raising ValueError on failure."""
    stripped = _strip_code_fences(text)
    return json.loads(stripped)


def _build_shopping_list(meal_plan) -> None:
    """
    Build (or rebuild) the shopping list for a MealPlan.
    Preserves is_checked for unchanged (ingredient_name, unit) items.
    All DB writes happen inside a transaction (caller is responsible for that).
    """
    from apps.shopping.models import ShoppingItem, ShoppingList

    # Preserve checked state
    preserved_checked = {}
    try:
        existing_list = meal_plan.shopping_list
        for item in existing_list.items.all():
            key = (item.ingredient_name, item.unit)
            preserved_checked[key] = item.is_checked
        existing_list.delete()
    except ShoppingList.DoesNotExist:
        pass

    # Aggregate ingredients
    aggregated: dict[tuple, dict] = defaultdict(
        lambda: {"total_quantity": 0.0, "category": "", "notes": ""}
    )

    _slot_order = ["breakfast", "lunch", "dinner", "afternoon_snack", "night_snack"]
    planned_meals = meal_plan.planned_meals.select_related("recipe").prefetch_related(
        "recipe__ingredients"
    )
    sorted_planned = sorted(
        planned_meals,
        key=lambda pm: (
            pm.day_offset,
            _slot_order.index(pm.meal_slot) if pm.meal_slot in _slot_order else 99,
        ),
    )
    for pm in sorted_planned:
        for ingredient in pm.recipe.ingredients.all():
            key = (ingredient.name, ingredient.unit)
            aggregated[key]["total_quantity"] += ingredient.quantity
            if not aggregated[key]["category"]:
                aggregated[key]["category"] = ingredient.category
            if not aggregated[key]["notes"] and ingredient.notes:
                aggregated[key]["notes"] = ingredient.notes

    shopping_list = ShoppingList.objects.create(meal_plan=meal_plan)
    for (name, unit), data in aggregated.items():
        key = (name, unit)
        is_checked = preserved_checked.get(key, False)
        ShoppingItem.objects.create(
            shopping_list=shopping_list,
            ingredient_name=name,
            total_quantity=data["total_quantity"],
            unit=unit,
            category=data["category"],
            is_checked=is_checked,
            notes=data["notes"],
        )


def aggregate_shopping_items(meal_plan) -> list[dict]:
    """
    Returns aggregated shopping items for a meal plan as a list of dicts.
    Used in tests. Does NOT write to DB.
    """
    aggregated: dict[tuple, dict] = defaultdict(
        lambda: {"total_quantity": 0.0, "category": "", "notes": ""}
    )

    slot_order = ["breakfast", "lunch", "dinner", "afternoon_snack", "night_snack"]
    planned_meals = meal_plan.planned_meals.select_related("recipe").prefetch_related(
        "recipe__ingredients"
    )
    # Sort by day_offset then meal slot order
    sorted_meals = sorted(
        planned_meals,
        key=lambda pm: (
            pm.day_offset,
            slot_order.index(pm.meal_slot) if pm.meal_slot in slot_order else 99,
        ),
    )
    for pm in sorted_meals:
        for ingredient in pm.recipe.ingredients.all():
            key = (ingredient.name, ingredient.unit)
            aggregated[key]["total_quantity"] += ingredient.quantity
            if not aggregated[key]["category"]:
                aggregated[key]["category"] = ingredient.category
            if not aggregated[key]["notes"] and ingredient.notes:
                aggregated[key]["notes"] = ingredient.notes

    result = []
    for (name, unit), data in aggregated.items():
        result.append(
            {
                "ingredient_name": name,
                "unit": unit,
                "total_quantity": data["total_quantity"],
                "category": data["category"],
                "notes": data["notes"],
            }
        )
    return result


def _save_plan(parsed: dict, nutrition_plan, week_start_date):
    """Persist a parsed week plan to the database. Must be called inside a transaction."""
    from apps.meals.models import Ingredient, MealPlan, PlannedMeal, Recipe

    # Archive existing active plan for this week
    MealPlan.objects.filter(
        nutrition_plan=nutrition_plan,
        week_start_date=week_start_date,
        status=MealPlan.STATUS_ACTIVE,
    ).update(status=MealPlan.STATUS_ARCHIVED)

    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date=week_start_date,
        status=MealPlan.STATUS_ACTIVE,
    )

    week_plan = parsed.get("week_plan", {})
    for day_key, day_data in week_plan.items():
        day_offset = int(day_key)
        for slot, meal_data in day_data.items():
            if not meal_data:
                continue
            recipe = Recipe.objects.create(
                name=meal_data.get("name", ""),
                description=meal_data.get("description", ""),
                instructions=meal_data.get("instructions", ""),
                prep_time_minutes=meal_data.get("prep_time_minutes", 0),
                cook_time_minutes=meal_data.get("cook_time_minutes", 0),
                servings=meal_data.get("servings", 1),
                meal_type=meal_data.get("meal_type", ""),
                cuisine_type=meal_data.get("cuisine_type", ""),
                calories=meal_data.get("calories", 0),
                protein_grams=meal_data.get("protein_grams", 0.0),
                carbs_grams=meal_data.get("carbs_grams", 0.0),
                fat_grams=meal_data.get("fat_grams", 0.0),
                fiber_grams=meal_data.get("fiber_grams"),
                sodium_mg=meal_data.get("sodium_mg"),
                tags=meal_data.get("tags", []),
            )
            for ing_data in meal_data.get("ingredients", []):
                Ingredient.objects.create(
                    recipe=recipe,
                    name=ing_data.get("name", ""),
                    quantity=ing_data.get("quantity", 0.0),
                    unit=ing_data.get("unit", ""),
                    notes=ing_data.get("notes", ""),
                    category=ing_data.get("category", ""),
                )
            PlannedMeal.objects.create(
                meal_plan=meal_plan,
                recipe=recipe,
                day_offset=day_offset,
                meal_slot=slot,
                is_optional=(slot == "night_snack"),
            )

    _build_shopping_list(meal_plan)
    return meal_plan


def generate_meal_plan(nutrition_plan, week_start_date):
    """
    Generate and persist a full week meal plan.
    Returns the created MealPlan instance.
    Raises ValueError on persistent failure.
    """
    from ai.client import get_client

    client = get_client()
    messages = [{"role": "user", "content": _build_user_message(nutrition_plan)}]

    # First attempt
    raw = _call_api(client, messages)
    try:
        parsed = _parse_response(raw)
    except (json.JSONDecodeError, ValueError):
        # Retry with correction message
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Your response was not valid JSON."
                    " Please respond with pure JSON only, no markdown."
                ),
            }
        )
        raw2 = _call_api(client, messages)
        try:
            parsed = _parse_response(raw2)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("Agent returned invalid JSON on two attempts.") from exc

    # Validate nutrition
    errors = _validate_nutrition(parsed, nutrition_plan)
    if errors:
        error_msg = (
            "The following daily nutrition totals are outside ±15% of targets:\n"
            + "\n".join(errors)
        )
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {"role": "user", "content": error_msg + "\nPlease regenerate with corrected macros."}
        )
        raw2 = _call_api(client, messages)
        try:
            parsed = _parse_response(raw2)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("Agent returned invalid JSON after nutrition correction.") from exc
        errors2 = _validate_nutrition(parsed, nutrition_plan)
        if errors2:
            raise ValueError(
                "Nutrition targets still not met after correction:\n" + "\n".join(errors2)
            )

    with transaction.atomic():
        return _save_plan(parsed, nutrition_plan, week_start_date)


def generate_swap(planned_meal, reason: str = "") -> None:
    """
    Swap a single PlannedMeal with a new recipe.
    Updates the PlannedMeal and regenerates the shopping list (preserving is_checked).
    Raises ValueError on persistent failure.
    """
    from ai.client import get_client
    from apps.meals.models import Ingredient, Recipe

    client = get_client()
    current_recipe_name = planned_meal.recipe.name
    meal_plan = planned_meal.meal_plan
    nutrition_plan = meal_plan.nutrition_plan
    snack_slots = ("afternoon_snack", "night_snack")
    meal_type_str = "snack" if planned_meal.meal_slot in snack_slots else planned_meal.meal_slot

    prompt = f"""Generate a single replacement meal for the {planned_meal.meal_slot} slot.

Current meal to replace (do NOT use this recipe): {current_recipe_name}
{"Reason for swap: " + reason if reason else ""}

Nutrition plan targets:
- daily_calories: {nutrition_plan.daily_calories}
- protein_grams: {nutrition_plan.protein_grams}
- carbs_grams: {nutrition_plan.carbs_grams}
- fat_grams: {nutrition_plan.fat_grams}
- max_cook_time_minutes: {nutrition_plan.max_cook_time_minutes}
- cooking_skill_level: {nutrition_plan.cooking_skill_level}
- dietary restrictions: vegetarian={nutrition_plan.is_vegetarian}, vegan={nutrition_plan.is_vegan},
  gluten_free={nutrition_plan.is_gluten_free}, dairy_free={nutrition_plan.is_dairy_free}
- allergies: {nutrition_plan.allergies}

IMPORTANT: Set servings: 1. Respond with pure JSON only.

Schema:
{{
  "name": "...",
  "description": "...",
  "instructions": "...",
  "prep_time_minutes": 0,
  "cook_time_minutes": 0,
  "servings": 1,
  "meal_type": "{meal_type_str}",
  "cuisine_type": "...",
  "calories": 0,
  "protein_grams": 0.0,
  "carbs_grams": 0.0,
  "fat_grams": 0.0,
  "fiber_grams": 0.0,
  "sodium_mg": 0.0,
  "tags": [],
  "ingredients": [
    {{"name": "...", "quantity": 0.0, "unit": "...", "category": "...", "notes": ""}}
  ]
}}
"""

    messages = [{"role": "user", "content": prompt}]

    raw = _call_api(client, messages)
    try:
        meal_data = _parse_response(raw)
    except (json.JSONDecodeError, ValueError):
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "user",
                "content": "Your response was not valid JSON. Please respond with pure JSON only.",
            }
        )
        raw2 = _call_api(client, messages)
        try:
            meal_data = _parse_response(raw2)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("Agent returned invalid JSON on two swap attempts.") from exc

    with transaction.atomic():
        recipe = Recipe.objects.create(
            name=meal_data.get("name", ""),
            description=meal_data.get("description", ""),
            instructions=meal_data.get("instructions", ""),
            prep_time_minutes=meal_data.get("prep_time_minutes", 0),
            cook_time_minutes=meal_data.get("cook_time_minutes", 0),
            servings=meal_data.get("servings", 1),
            meal_type=meal_data.get("meal_type", ""),
            cuisine_type=meal_data.get("cuisine_type", ""),
            calories=meal_data.get("calories", 0),
            protein_grams=meal_data.get("protein_grams", 0.0),
            carbs_grams=meal_data.get("carbs_grams", 0.0),
            fat_grams=meal_data.get("fat_grams", 0.0),
            fiber_grams=meal_data.get("fiber_grams"),
            sodium_mg=meal_data.get("sodium_mg"),
            tags=meal_data.get("tags", []),
        )
        for ing_data in meal_data.get("ingredients", []):
            Ingredient.objects.create(
                recipe=recipe,
                name=ing_data.get("name", ""),
                quantity=ing_data.get("quantity", 0.0),
                unit=ing_data.get("unit", ""),
                notes=ing_data.get("notes", ""),
                category=ing_data.get("category", ""),
            )

        planned_meal.recipe = recipe
        planned_meal.was_swapped = True
        if reason:
            planned_meal.swap_reason = reason
        planned_meal.save()

        _build_shopping_list(meal_plan)
