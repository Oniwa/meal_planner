import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai.meal_planner_agent import (
    _build_user_message,
    _strip_code_fences,
    _validate_nutrition,
    aggregate_shopping_items,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _make_mock_response(text: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=text)]
    return mock_resp


# --- Code fence stripping ---


def test_strip_code_fences_removes_json_fences():
    raw = '```json\n{"key": "value"}\n```'
    result = _strip_code_fences(raw)
    assert result == '{"key": "value"}'


def test_strip_code_fences_removes_plain_fences():
    raw = '```\n{"key": "value"}\n```'
    result = _strip_code_fences(raw)
    assert result == '{"key": "value"}'


def test_strip_code_fences_leaves_plain_json_unchanged():
    raw = '{"key": "value"}'
    result = _strip_code_fences(raw)
    assert result == '{"key": "value"}'


# --- Notes in prompt ---


@pytest.mark.django_db
def test_notes_injected_when_nonempty(sample_nutrition_plan):
    sample_nutrition_plan.notes = "Prefer Mediterranean flavors"
    sample_nutrition_plan.save()
    message = _build_user_message(sample_nutrition_plan)
    assert "Prefer Mediterranean flavors" in message
    assert '"notes"' in message


@pytest.mark.django_db
def test_notes_omitted_when_empty(sample_nutrition_plan):
    sample_nutrition_plan.notes = ""
    sample_nutrition_plan.save()
    message = _build_user_message(sample_nutrition_plan)
    # When notes is empty, the "notes" key should not appear in the plan data JSON
    # Parse out the plan data section: it's embedded as JSON.dumps(plan_data)

    # The plan_data object is serialized with indent=2 as part of the message.
    # When notes is absent, the plan_data dict won't have a "notes" key.
    # We check the plan data doesn't contain the notes key by looking for it
    # right after common plan keys like "include_night_snack".
    assert '"notes": ""' not in message
    assert '"notes": "Prefer' not in message


# --- Nutrition validation ---


@pytest.fixture
def nutrition_plan_2000(db):
    from apps.nutrition.models import NutritionPlan

    return NutritionPlan.objects.create(
        label="Test",
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
    )


def _make_parsed_good(calories=2000, protein=150, carbs=200, fat=65):
    summary = {}
    for i in range(7):
        summary[str(i)] = {
            "calories": calories,
            "protein_grams": protein,
            "carbs_grams": carbs,
            "fat_grams": fat,
        }
    return {"week_plan": {}, "daily_nutrition_summary": summary}


def test_nutrition_validation_passes_within_tolerance(nutrition_plan_2000):
    parsed = _make_parsed_good(calories=2000, protein=150, carbs=200, fat=65)
    errors = _validate_nutrition(parsed, nutrition_plan_2000)
    assert errors == []


def test_nutrition_validation_passes_at_lower_bound(nutrition_plan_2000):
    # Exactly at 15% below target (use ceil to stay within bound)
    import math

    parsed = _make_parsed_good(
        calories=math.ceil(2000 * 0.85),
        protein=math.ceil(150 * 0.85),
        carbs=math.ceil(200 * 0.85),
        fat=math.ceil(65 * 0.85),
    )
    errors = _validate_nutrition(parsed, nutrition_plan_2000)
    assert errors == []


def test_nutrition_validation_passes_at_upper_bound(nutrition_plan_2000):
    # Exactly at 15% above target (use floor to stay within bound)
    import math

    parsed = _make_parsed_good(
        calories=math.floor(2000 * 1.15),
        protein=math.floor(150 * 1.15),
        carbs=math.floor(200 * 1.15),
        fat=math.floor(65 * 1.15),
    )
    errors = _validate_nutrition(parsed, nutrition_plan_2000)
    assert errors == []


def test_nutrition_validation_fails_when_calories_too_low(nutrition_plan_2000):
    parsed = _make_parsed_good(calories=1000, protein=150, carbs=200, fat=65)
    errors = _validate_nutrition(parsed, nutrition_plan_2000)
    assert len(errors) > 0
    assert any("calories" in e for e in errors)


def test_nutrition_validation_fails_on_bad_nutrition_fixture(nutrition_plan_2000):
    fixture_path = FIXTURES_DIR / "week_plan_bad_nutrition.json"
    parsed = json.loads(fixture_path.read_text())
    errors = _validate_nutrition(parsed, nutrition_plan_2000)
    assert len(errors) > 0


# --- generate_meal_plan retry logic ---


@pytest.mark.django_db
def test_json_decode_error_on_first_call_retries(mock_anthropic_client, sample_nutrition_plan):
    import datetime

    from ai.meal_planner_agent import generate_meal_plan

    invalid_txt = (FIXTURES_DIR / "week_plan_invalid_json.txt").read_text()
    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()

    resp_invalid = _make_mock_response(invalid_txt)
    resp_valid = _make_mock_response(valid_json)

    mock_anthropic_client.messages.create.side_effect = [resp_invalid, resp_valid]

    week_start = datetime.date(2026, 4, 6)
    plan = generate_meal_plan(sample_nutrition_plan, week_start)

    assert plan is not None
    assert mock_anthropic_client.messages.create.call_count == 2


@pytest.mark.django_db
def test_json_decode_error_on_second_call_raises(mock_anthropic_client, sample_nutrition_plan):
    import datetime

    from ai.meal_planner_agent import generate_meal_plan

    invalid_txt = (FIXTURES_DIR / "week_plan_invalid_json.txt").read_text()
    resp_invalid1 = _make_mock_response(invalid_txt)
    resp_invalid2 = _make_mock_response(invalid_txt)

    mock_anthropic_client.messages.create.side_effect = [resp_invalid1, resp_invalid2]

    week_start = datetime.date(2026, 4, 6)
    with pytest.raises(ValueError, match="invalid JSON"):
        generate_meal_plan(sample_nutrition_plan, week_start)


@pytest.mark.django_db
def test_bad_nutrition_retries_with_correction(mock_anthropic_client, sample_nutrition_plan):
    import datetime

    from ai.meal_planner_agent import generate_meal_plan

    bad_json = (FIXTURES_DIR / "week_plan_bad_nutrition.json").read_text()
    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()

    resp_bad = _make_mock_response(bad_json)
    resp_valid = _make_mock_response(valid_json)

    mock_anthropic_client.messages.create.side_effect = [resp_bad, resp_valid]

    week_start = datetime.date(2026, 4, 6)
    plan = generate_meal_plan(sample_nutrition_plan, week_start)

    assert plan is not None
    assert mock_anthropic_client.messages.create.call_count == 2
    # Verify the second call included a correction message
    second_call_args = mock_anthropic_client.messages.create.call_args_list[1]
    messages = (
        second_call_args.kwargs.get("messages") or second_call_args.args[0]
        if second_call_args.args
        else second_call_args.kwargs["messages"]
    )
    # Find correction in messages list
    message_contents = [m.get("content", "") for m in messages]
    assert any("±15%" in c or "targets" in c.lower() for c in message_contents)


@pytest.mark.django_db
def test_bad_nutrition_twice_raises(mock_anthropic_client, sample_nutrition_plan):
    import datetime

    from ai.meal_planner_agent import generate_meal_plan

    bad_json = (FIXTURES_DIR / "week_plan_bad_nutrition.json").read_text()
    resp_bad1 = _make_mock_response(bad_json)
    resp_bad2 = _make_mock_response(bad_json)

    mock_anthropic_client.messages.create.side_effect = [resp_bad1, resp_bad2]

    week_start = datetime.date(2026, 4, 6)
    with pytest.raises(ValueError):
        generate_meal_plan(sample_nutrition_plan, week_start)


# --- generate_swap ---


@pytest.mark.django_db
def test_generate_swap_excludes_current_recipe_name(mock_anthropic_client, sample_nutrition_plan):
    import datetime

    from ai.meal_planner_agent import generate_meal_plan, generate_swap

    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()
    swap_json = (FIXTURES_DIR / "swap_response.json").read_text()

    resp_valid = _make_mock_response(valid_json)
    resp_swap = _make_mock_response(swap_json)

    mock_anthropic_client.messages.create.side_effect = [resp_valid, resp_swap]

    week_start = datetime.date(2026, 4, 6)
    plan = generate_meal_plan(sample_nutrition_plan, week_start)

    planned_meal = plan.planned_meals.first()
    original_name = planned_meal.recipe.name

    generate_swap(planned_meal)

    # Check that the swap prompt excluded the original recipe name
    swap_call_args = mock_anthropic_client.messages.create.call_args_list[1]
    messages = swap_call_args.kwargs.get("messages") or swap_call_args.kwargs["messages"]
    message_contents = [m.get("content", "") for m in messages]
    assert any(original_name in c for c in message_contents)
    assert any("do NOT use" in c or "NOT" in c for c in message_contents)


# --- Shopping aggregation ---


@pytest.mark.django_db
def test_shopping_aggregation_same_name_and_unit(db):
    from apps.meals.models import Ingredient, MealPlan, PlannedMeal, Recipe
    from apps.nutrition.models import NutritionPlan

    nutrition_plan = NutritionPlan.objects.create(
        label="Test",
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
    )

    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date="2026-04-06",
    )

    recipe1 = Recipe.objects.create(name="Recipe 1", calories=300)
    Ingredient.objects.create(
        recipe=recipe1, name="chicken breast", quantity=6.0, unit="oz", category="protein"
    )

    recipe2 = Recipe.objects.create(name="Recipe 2", calories=400)
    Ingredient.objects.create(
        recipe=recipe2, name="chicken breast", quantity=4.0, unit="oz", category="protein"
    )

    PlannedMeal.objects.create(meal_plan=meal_plan, recipe=recipe1, day_offset=0, meal_slot="lunch")
    PlannedMeal.objects.create(
        meal_plan=meal_plan, recipe=recipe2, day_offset=0, meal_slot="dinner"
    )

    items = aggregate_shopping_items(meal_plan)

    chicken_items = [i for i in items if i["ingredient_name"] == "chicken breast"]
    assert len(chicken_items) == 1
    assert chicken_items[0]["total_quantity"] == 10.0
    assert chicken_items[0]["unit"] == "oz"


@pytest.mark.django_db
def test_shopping_aggregation_same_name_different_units(db):
    from apps.meals.models import Ingredient, MealPlan, PlannedMeal, Recipe
    from apps.nutrition.models import NutritionPlan

    nutrition_plan = NutritionPlan.objects.create(
        label="Test",
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
    )

    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date="2026-04-06",
    )

    recipe1 = Recipe.objects.create(name="Recipe 1", calories=300)
    Ingredient.objects.create(
        recipe=recipe1, name="olive oil", quantity=2.0, unit="tbsp", category="fat"
    )

    recipe2 = Recipe.objects.create(name="Recipe 2", calories=400)
    Ingredient.objects.create(
        recipe=recipe2, name="olive oil", quantity=1.0, unit="cup", category="fat"
    )

    PlannedMeal.objects.create(meal_plan=meal_plan, recipe=recipe1, day_offset=0, meal_slot="lunch")
    PlannedMeal.objects.create(
        meal_plan=meal_plan, recipe=recipe2, day_offset=0, meal_slot="dinner"
    )

    items = aggregate_shopping_items(meal_plan)

    oil_items = [i for i in items if i["ingredient_name"] == "olive oil"]
    assert len(oil_items) == 2


@pytest.mark.django_db
def test_shopping_aggregation_empty_plan(db):
    from apps.meals.models import MealPlan
    from apps.nutrition.models import NutritionPlan

    nutrition_plan = NutritionPlan.objects.create(
        label="Test",
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
    )

    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date="2026-04-06",
    )

    items = aggregate_shopping_items(meal_plan)
    assert items == []


@pytest.mark.django_db
def test_shopping_item_notes_first_nonempty_wins(db):
    from apps.meals.models import Ingredient, MealPlan, PlannedMeal, Recipe
    from apps.nutrition.models import NutritionPlan

    nutrition_plan = NutritionPlan.objects.create(
        label="Test",
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
    )

    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date="2026-04-06",
    )

    recipe1 = Recipe.objects.create(name="Recipe 1", calories=300)
    Ingredient.objects.create(
        recipe=recipe1,
        name="soy sauce",
        quantity=1.0,
        unit="tbsp",
        category="pantry",
        notes="low-sodium",
    )

    recipe2 = Recipe.objects.create(name="Recipe 2", calories=400)
    Ingredient.objects.create(
        recipe=recipe2,
        name="soy sauce",
        quantity=2.0,
        unit="tbsp",
        category="pantry",
        notes="organic",
    )

    PlannedMeal.objects.create(meal_plan=meal_plan, recipe=recipe1, day_offset=0, meal_slot="lunch")
    PlannedMeal.objects.create(
        meal_plan=meal_plan, recipe=recipe2, day_offset=0, meal_slot="dinner"
    )

    items = aggregate_shopping_items(meal_plan)

    soy_items = [i for i in items if i["ingredient_name"] == "soy sauce"]
    assert len(soy_items) == 1
    assert soy_items[0]["notes"] == "low-sodium"


@pytest.mark.django_db
def test_shopping_item_notes_all_empty_gives_blank(db):
    from apps.meals.models import Ingredient, MealPlan, PlannedMeal, Recipe
    from apps.nutrition.models import NutritionPlan

    nutrition_plan = NutritionPlan.objects.create(
        label="Test",
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
    )

    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date="2026-04-06",
    )

    recipe1 = Recipe.objects.create(name="Recipe 1", calories=300)
    Ingredient.objects.create(
        recipe=recipe1, name="salt", quantity=0.5, unit="tsp", category="pantry", notes=""
    )

    recipe2 = Recipe.objects.create(name="Recipe 2", calories=400)
    Ingredient.objects.create(
        recipe=recipe2, name="salt", quantity=0.5, unit="tsp", category="pantry", notes=""
    )

    PlannedMeal.objects.create(meal_plan=meal_plan, recipe=recipe1, day_offset=0, meal_slot="lunch")
    PlannedMeal.objects.create(
        meal_plan=meal_plan, recipe=recipe2, day_offset=0, meal_slot="dinner"
    )

    items = aggregate_shopping_items(meal_plan)

    salt_items = [i for i in items if i["ingredient_name"] == "salt"]
    assert len(salt_items) == 1
    assert salt_items[0]["notes"] == ""
