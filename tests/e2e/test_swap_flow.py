import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _seed_meal_plan(nutrition_plan):
    from apps.meals.models import Ingredient, MealPlan, PlannedMeal, Recipe
    from apps.shopping.models import ShoppingItem, ShoppingList

    week_start = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date=week_start,
        status="active",
    )

    recipe = Recipe.objects.create(
        name="Original Breakfast Meal",
        calories=420,
        protein_grams=32.0,
        carbs_grams=45.0,
        fat_grams=10.0,
    )
    Ingredient.objects.create(
        recipe=recipe, name="eggs", quantity=3.0, unit="large", category="protein"
    )

    for day_offset in range(7):
        for slot in ["breakfast", "lunch", "dinner", "afternoon_snack"]:
            r = Recipe.objects.create(
                name=f"Day {day_offset} {slot}",
                calories=400,
                protein_grams=30.0,
                carbs_grams=50.0,
                fat_grams=10.0,
            )
            PlannedMeal.objects.create(
                meal_plan=meal_plan, recipe=r, day_offset=day_offset, meal_slot=slot
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


@pytest.fixture
def seeded_plan_and_nutrition(db):
    from apps.nutrition.models import NutritionPlan

    np = NutritionPlan.objects.create(
        label="E2E Swap Test",
        is_active=True,
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
        include_night_snack=False,
    )
    mp = _seed_meal_plan(np)
    return np, mp


@pytest.mark.django_db
def test_swap_updates_cell_in_place(
    page, live_server, seeded_plan_and_nutrition, mock_anthropic_client
):
    """Click Swap on a meal cell — cell updates in-place (HTMX), no full reload."""
    np, mp = seeded_plan_and_nutrition
    swap_json = (FIXTURES_DIR / "swap_response.json").read_text()

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=swap_json)]
    mock_anthropic_client.messages.create.return_value = mock_resp

    page.goto(f"{live_server.url}/meals/")

    # Find the first Swap button
    swap_buttons = page.locator(".swap-btn")
    assert swap_buttons.count() > 0

    # Get the initial URL to verify no full reload
    initial_url = page.url

    swap_buttons.first.click()

    # Wait for HTMX to update the cell
    page.wait_for_timeout(2000)

    # URL should not have changed (in-place update)
    assert page.url == initial_url

    # The new meal name from swap_response.json should appear
    content = page.content()
    assert "Tofu Scramble" in content
