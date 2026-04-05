import datetime

import pytest
from django.urls import reverse


def _make_shopping_setup(nutrition_plan):
    from apps.meals.models import MealPlan, PlannedMeal, Recipe
    from apps.shopping.models import ShoppingItem, ShoppingList

    week_start = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    meal_plan = MealPlan.objects.create(
        nutrition_plan=nutrition_plan,
        week_start_date=week_start,
        status="active",
    )
    recipe = Recipe.objects.create(name="Test Meal", calories=400)
    PlannedMeal.objects.create(
        meal_plan=meal_plan, recipe=recipe, day_offset=0, meal_slot="breakfast"
    )

    sl = ShoppingList.objects.create(meal_plan=meal_plan)
    item1 = ShoppingItem.objects.create(
        shopping_list=sl,
        ingredient_name="chicken breast",
        total_quantity=42.0,
        unit="oz",
        category="protein",
    )
    item2 = ShoppingItem.objects.create(
        shopping_list=sl,
        ingredient_name="broccoli",
        total_quantity=7.0,
        unit="cup",
        category="produce",
    )
    item3 = ShoppingItem.objects.create(
        shopping_list=sl,
        ingredient_name="olive oil",
        total_quantity=7.0,
        unit="tbsp",
        category="fat",
    )
    return meal_plan, sl, [item1, item2, item3]


@pytest.mark.django_db
def test_get_shopping_list_returns_200(client, sample_nutrition_plan):
    _make_shopping_setup(sample_nutrition_plan)
    response = client.get(reverse("shopping_list"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_shopping_list_items_grouped_by_category(client, sample_nutrition_plan):
    _make_shopping_setup(sample_nutrition_plan)
    response = client.get(reverse("shopping_list"))
    content = response.content.decode()

    assert "protein" in content
    assert "produce" in content
    assert "chicken breast" in content
    assert "broccoli" in content


@pytest.mark.django_db
def test_post_toggle_check_changes_is_checked(client, sample_nutrition_plan):

    _, sl, items = _make_shopping_setup(sample_nutrition_plan)
    item = items[0]
    assert not item.is_checked

    response = client.post(
        reverse("shopping_check"),
        data={"item_id": item.id},
    )

    assert response.status_code == 200
    item.refresh_from_db()
    assert item.is_checked is True


@pytest.mark.django_db
def test_post_toggle_check_returns_htmx_fragment(client, sample_nutrition_plan):
    _, sl, items = _make_shopping_setup(sample_nutrition_plan)
    item = items[0]

    response = client.post(
        reverse("shopping_check"),
        data={"item_id": item.id},
    )

    assert response.status_code == 200
    content = response.content.decode()
    # Should be a fragment, not a full page
    assert "<!DOCTYPE html>" not in content
    assert "chicken breast" in content


@pytest.mark.django_db
def test_post_toggle_check_twice_restores_original(client, sample_nutrition_plan):

    _, sl, items = _make_shopping_setup(sample_nutrition_plan)
    item = items[0]

    # Toggle on
    client.post(reverse("shopping_check"), data={"item_id": item.id})
    item.refresh_from_db()
    assert item.is_checked is True

    # Toggle off
    client.post(reverse("shopping_check"), data={"item_id": item.id})
    item.refresh_from_db()
    assert item.is_checked is False
