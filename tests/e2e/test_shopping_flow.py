import datetime

import pytest


def _seed_shopping(db):
    from apps.meals.models import MealPlan, PlannedMeal, Recipe
    from apps.nutrition.models import NutritionPlan
    from apps.shopping.models import ShoppingItem, ShoppingList

    np = NutritionPlan.objects.create(
        label="E2E Shopping Test",
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
    week_start = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    mp = MealPlan.objects.create(nutrition_plan=np, week_start_date=week_start, status="active")
    r = Recipe.objects.create(name="Test Meal", calories=400)
    PlannedMeal.objects.create(meal_plan=mp, recipe=r, day_offset=0, meal_slot="breakfast")

    sl = ShoppingList.objects.create(meal_plan=mp)
    item = ShoppingItem.objects.create(
        shopping_list=sl,
        ingredient_name="salmon fillet",
        total_quantity=42.0,
        unit="oz",
        category="protein",
    )
    return item


@pytest.mark.django_db
def test_check_item_persists_after_reload(page, live_server, db):
    """Check off an item — checkbox state persists after page reload."""
    item = _seed_shopping(db)

    page.goto(f"{live_server.url}/shopping/")

    # Find the check button for our item
    assert "salmon fillet" in page.content()

    # Click the check button for the item
    check_button = page.locator(f"button[hx-vals*='{item.id}']").first
    check_button.click()

    # Wait for HTMX to update
    page.wait_for_timeout(1000)

    # The item should now show as struck-through / checked
    content = page.content()
    assert "line-through" in content or "checked" in content.lower() or "bg-green" in content

    # Reload the page
    page.reload()
    page.wait_for_load_state("networkidle")

    # Verify persistence
    item.refresh_from_db()
    assert item.is_checked is True

    content = page.content()
    assert "line-through" in content or "bg-green" in content
