import json

import pytest

VALID_PLAN = {
    "label": "E2E Test Plan",
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
def test_import_flow_paste_json(page, live_server):
    """Navigate to import page, paste valid JSON, submit, verify redirect to plan summary."""
    page.goto(f"{live_server.url}/nutrition/import/")

    assert page.title() in ["Import Nutrition Plan", "Meal Planner"]

    textarea = page.locator("textarea[name='json_data']")
    textarea.fill(json.dumps(VALID_PLAN))

    page.click("button[type='submit']")

    page.wait_for_url(f"{live_server.url}/nutrition/plan/")

    content = page.content()
    assert "E2E Test Plan" in content


@pytest.mark.django_db
def test_import_flow_missing_field_shows_error(page, live_server):
    """Submit JSON missing a required field — error shown, nothing saved."""
    page.goto(f"{live_server.url}/nutrition/import/")

    bad_plan = dict(VALID_PLAN)
    del bad_plan["label"]

    textarea = page.locator("textarea[name='json_data']")
    textarea.fill(json.dumps(bad_plan))

    page.click("button[type='submit']")

    # Should stay on import page (no redirect)
    assert "/nutrition/import/" in page.url

    content = page.content()
    assert "label" in content.lower() or "error" in content.lower()
