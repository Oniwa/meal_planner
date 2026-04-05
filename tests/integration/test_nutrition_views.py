import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_get_import_page_returns_200(client):
    response = client.get(reverse("nutrition_import"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_import_page_has_form(client):
    response = client.get(reverse("nutrition_import"))
    content = response.content.decode()
    assert "<form" in content
    assert "json_data" in content


VALID_PLAN = {
    "label": "Test Plan - April 2026",
    "daily_calories": 2000,
    "protein_grams": 150,
    "carbs_grams": 200,
    "fat_grams": 65,
    "max_cook_time_minutes": 45,
    "cooking_skill_level": "intermediate",
    "meal_variety": "medium",
    "include_night_snack": False,
}


@pytest.mark.django_db
def test_post_valid_json_saves_plan(client):
    from apps.nutrition.models import NutritionPlan

    response = client.post(
        reverse("nutrition_import"),
        data={"json_data": json.dumps(VALID_PLAN)},
    )
    assert response.status_code == 302
    assert response.url == reverse("nutrition_plan")
    assert NutritionPlan.objects.filter(label="Test Plan - April 2026").exists()


@pytest.mark.django_db
def test_post_valid_json_deactivates_previous_plan(client):
    from apps.nutrition.models import NutritionPlan

    # Create an existing active plan
    old_plan = NutritionPlan.objects.create(
        label="Old Plan",
        is_active=True,
        daily_calories=1800,
        protein_grams=120,
        carbs_grams=180,
        fat_grams=60,
        max_cook_time_minutes=30,
        cooking_skill_level="beginner",
        meal_variety="low",
        include_night_snack=False,
    )

    client.post(
        reverse("nutrition_import"),
        data={"json_data": json.dumps(VALID_PLAN)},
    )

    old_plan.refresh_from_db()
    assert not old_plan.is_active

    new_plan = NutritionPlan.objects.get(label="Test Plan - April 2026")
    assert new_plan.is_active


@pytest.mark.django_db
def test_post_missing_required_field_returns_200_with_error(client):
    from apps.nutrition.models import NutritionPlan

    bad_data = dict(VALID_PLAN)
    del bad_data["label"]

    response = client.post(
        reverse("nutrition_import"),
        data={"json_data": json.dumps(bad_data)},
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "label" in content
    assert not NutritionPlan.objects.exists()


@pytest.mark.django_db
def test_post_invalid_json_returns_200_with_error(client):
    from apps.nutrition.models import NutritionPlan

    response = client.post(
        reverse("nutrition_import"),
        data={"json_data": "this is not json { broken"},
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Invalid JSON" in content or "JSON" in content
    assert not NutritionPlan.objects.exists()


@pytest.mark.django_db
def test_get_plan_summary_with_active_plan(client, sample_nutrition_plan):
    response = client.get(reverse("nutrition_plan"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Plan - April 2026" in content


@pytest.mark.django_db
def test_get_plan_summary_no_active_plan_redirects(client):
    response = client.get(reverse("nutrition_plan"))
    assert response.status_code == 302
    assert response.url == reverse("nutrition_import")


@pytest.mark.django_db
def test_plan_summary_shows_macros(client, sample_nutrition_plan):
    response = client.get(reverse("nutrition_plan"))
    content = response.content.decode()
    assert "2000" in content  # calories
    assert "150" in content  # protein
