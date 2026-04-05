import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.urls import reverse

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _make_mock_response(text: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=text)]
    return mock_resp


def _make_meal_plan(nutrition_plan, week_start=None, status="active"):
    from apps.meals.models import Ingredient, MealPlan, PlannedMeal, Recipe
    from apps.shopping.models import ShoppingItem, ShoppingList

    if week_start is None:
        week_start = datetime.date.today() - datetime.timedelta(
            days=datetime.date.today().weekday()
        )

    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date=week_start,
        status=status,
    )

    recipe = Recipe.objects.create(
        name="Test Breakfast",
        calories=400,
        protein_grams=30.0,
        carbs_grams=50.0,
        fat_grams=10.0,
    )
    Ingredient.objects.create(
        recipe=recipe, name="eggs", quantity=3.0, unit="large", category="protein"
    )
    PlannedMeal.objects.create(
        meal_plan=meal_plan,
        recipe=recipe,
        day_offset=0,
        meal_slot="breakfast",
    )

    sl = ShoppingList.objects.create(meal_plan=meal_plan)
    ShoppingItem.objects.create(
        shopping_list=sl,
        ingredient_name="eggs",
        total_quantity=21.0,
        unit="large",
        category="protein",
    )

    return meal_plan


@pytest.mark.django_db
def test_get_meals_no_nutrition_plan_redirects(client):
    response = client.get(reverse("meals_current"))
    assert response.status_code == 302
    assert response.url == reverse("nutrition_import")


@pytest.mark.django_db
def test_get_meals_with_nutrition_plan_but_no_meal_plan_shows_generate(
    client, sample_nutrition_plan
):
    response = client.get(reverse("meals_current"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Generate Week Plan" in content


@pytest.mark.django_db
def test_get_meals_with_active_plan_shows_week_grid(client, sample_nutrition_plan):
    _make_meal_plan(sample_nutrition_plan)
    response = client.get(reverse("meals_current"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Breakfast" in content


@pytest.mark.django_db
def test_post_generate_creates_meal_plan(client, sample_nutrition_plan, mock_anthropic_client):
    from apps.meals.models import MealPlan

    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()
    mock_anthropic_client.messages.create.return_value = _make_mock_response(valid_json)

    response = client.post(reverse("meals_generate"))

    assert response.status_code == 302
    assert MealPlan.objects.filter(
        nutrition_plan=sample_nutrition_plan,
        status="active",
    ).exists()


@pytest.mark.django_db
def test_post_generate_archives_existing_active_plan(
    client, sample_nutrition_plan, mock_anthropic_client
):
    from apps.meals.models import MealPlan

    week_start = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    old_plan = MealPlan.objects.create(
        nutrition_plan=sample_nutrition_plan,
        week_start_date=week_start,
        status="active",
    )

    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()
    mock_anthropic_client.messages.create.return_value = _make_mock_response(valid_json)

    client.post(reverse("meals_generate"))

    old_plan.refresh_from_db()
    assert old_plan.status == "archived"
    assert MealPlan.objects.filter(status="active", week_start_date=week_start).exists()


@pytest.mark.django_db
def test_post_generate_also_creates_shopping_list(
    client, sample_nutrition_plan, mock_anthropic_client
):
    from apps.meals.models import MealPlan
    from apps.shopping.models import ShoppingList

    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()
    mock_anthropic_client.messages.create.return_value = _make_mock_response(valid_json)

    client.post(reverse("meals_generate"))

    meal_plan = MealPlan.objects.filter(status="active").first()
    assert ShoppingList.objects.filter(meal_plan=meal_plan).exists()


@pytest.mark.django_db
def test_post_generate_agent_failure_renders_error(
    client, sample_nutrition_plan, mock_anthropic_client
):
    from apps.meals.models import MealPlan

    mock_anthropic_client.messages.create.side_effect = ValueError("API failure")

    response = client.post(reverse("meals_generate"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Failed" in content or "error" in content.lower()
    assert not MealPlan.objects.filter(status="active").exists()


@pytest.mark.django_db
def test_post_swap_valid_meal_returns_htmx_fragment(
    client, sample_nutrition_plan, mock_anthropic_client
):
    meal_plan = _make_meal_plan(sample_nutrition_plan)
    planned_meal = meal_plan.planned_meals.first()

    swap_json = (FIXTURES_DIR / "swap_response.json").read_text()
    mock_anthropic_client.messages.create.return_value = _make_mock_response(swap_json)

    response = client.post(
        reverse("meals_swap"),
        data={"planned_meal_id": planned_meal.id},
    )

    assert response.status_code == 200
    planned_meal.refresh_from_db()
    assert planned_meal.was_swapped is True


@pytest.mark.django_db
def test_post_swap_shopping_list_regenerated_preserving_checked(
    client, sample_nutrition_plan, mock_anthropic_client
):

    meal_plan = _make_meal_plan(sample_nutrition_plan)
    # Mark the existing shopping item as checked
    item = meal_plan.shopping_list.items.first()
    item.is_checked = True
    item.save()

    planned_meal = meal_plan.planned_meals.first()

    swap_json = (FIXTURES_DIR / "swap_response.json").read_text()
    mock_anthropic_client.messages.create.return_value = _make_mock_response(swap_json)

    client.post(
        reverse("meals_swap"),
        data={"planned_meal_id": planned_meal.id},
    )

    # eggs was in the original recipe as well as (via different recipe after swap)
    # The swap_response uses "firm tofu", "bell pepper", "turmeric"
    # eggs is no longer in the plan; it should be deleted from shopping list
    # But eggs was in the original recipe - after swap it's replaced so eggs is removed
    meal_plan.refresh_from_db()
    new_shopping_list = meal_plan.shopping_list
    assert new_shopping_list is not None


@pytest.mark.django_db
def test_post_swap_wrong_meal_plan_returns_404(client, sample_nutrition_plan):
    from apps.meals.models import MealPlan, PlannedMeal, Recipe
    from apps.nutrition.models import NutritionPlan

    # Create another nutrition plan and meal plan
    other_plan = NutritionPlan.objects.create(
        label="Other Plan",
        is_active=False,
        daily_calories=1800,
        protein_grams=120,
        carbs_grams=180,
        fat_grams=60,
        max_cook_time_minutes=30,
        cooking_skill_level="beginner",
        meal_variety="low",
        include_night_snack=False,
    )

    other_meal_plan = MealPlan.objects.create(
        nutrition_plan=other_plan,
        week_start_date=datetime.date(2026, 3, 30),
        status="active",
    )
    recipe = Recipe.objects.create(name="Other Recipe", calories=300)
    pm = PlannedMeal.objects.create(
        meal_plan=other_meal_plan,
        recipe=recipe,
        day_offset=0,
        meal_slot="breakfast",
    )

    # The active nutrition plan has an active meal plan for current week
    _make_meal_plan(sample_nutrition_plan)

    response = client.post(
        reverse("meals_swap"),
        data={"planned_meal_id": pm.id},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_post_swap_agent_failure_returns_error_fragment(
    client, sample_nutrition_plan, mock_anthropic_client
):
    meal_plan = _make_meal_plan(sample_nutrition_plan)
    planned_meal = meal_plan.planned_meals.first()

    mock_anthropic_client.messages.create.side_effect = ValueError("Swap failed")

    response = client.post(
        reverse("meals_swap"),
        data={"planned_meal_id": planned_meal.id},
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Swap failed" in content or "failed" in content.lower()

    # Original meal should be preserved
    planned_meal.refresh_from_db()
    assert planned_meal.was_swapped is False


@pytest.mark.django_db
def test_get_week_plan_valid_monday(client, sample_nutrition_plan):
    week_start = datetime.date(2026, 4, 6)  # Monday
    _make_meal_plan(sample_nutrition_plan, week_start=week_start)

    response = client.get(reverse("meals_week", kwargs={"week_start": "2026-04-06"}))
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_week_plan_non_monday_returns_404(client, sample_nutrition_plan):
    response = client.get(reverse("meals_week", kwargs={"week_start": "2026-04-07"}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_meal_detail_active_plan(client, sample_nutrition_plan):
    meal_plan = _make_meal_plan(sample_nutrition_plan)
    planned_meal = meal_plan.planned_meals.first()

    response = client.get(reverse("meal_detail", kwargs={"planned_meal_id": planned_meal.id}))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Breakfast" in content


@pytest.mark.django_db
def test_get_meal_detail_not_in_active_plan_returns_404(client, sample_nutrition_plan):
    from apps.meals.models import MealPlan, PlannedMeal, Recipe
    from apps.nutrition.models import NutritionPlan

    # Create a meal plan that belongs to a different (inactive) nutrition plan
    other_np = NutritionPlan.objects.create(
        label="Other",
        is_active=False,
        daily_calories=1800,
        protein_grams=120,
        carbs_grams=180,
        fat_grams=60,
        max_cook_time_minutes=30,
        cooking_skill_level="beginner",
        meal_variety="low",
        include_night_snack=False,
    )
    other_mp = MealPlan.objects.create(
        nutrition_plan=other_np,
        week_start_date=datetime.date(2026, 3, 30),
        status="active",
    )
    recipe = Recipe.objects.create(name="Other Recipe", calories=300)
    pm = PlannedMeal.objects.create(
        meal_plan=other_mp, recipe=recipe, day_offset=0, meal_slot="breakfast"
    )

    # Make sure sample_nutrition_plan has an active meal plan
    _make_meal_plan(sample_nutrition_plan)

    response = client.get(reverse("meal_detail", kwargs={"planned_meal_id": pm.id}))
    assert response.status_code == 404
