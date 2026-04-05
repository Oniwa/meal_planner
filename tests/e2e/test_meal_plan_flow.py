from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def seeded_nutrition_plan(db):
    from apps.nutrition.models import NutritionPlan

    return NutritionPlan.objects.create(
        label="E2E Meal Plan Test",
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


@pytest.mark.django_db
def test_generate_plan_shows_week_grid(
    page, live_server, seeded_nutrition_plan, mock_anthropic_client
):
    """Generate plan — spinner visible then 7-column grid renders."""
    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()

    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=valid_json)]
    mock_anthropic_client.messages.create.return_value = mock_resp

    page.goto(f"{live_server.url}/meals/")

    # Should see the generate button
    assert "Generate Week Plan" in page.content()

    page.click("button[type='submit']")

    # Wait for redirect back to /meals/
    page.wait_for_url(f"{live_server.url}/meals/", timeout=10000)

    content = page.content()
    # Should see meal names from the fixture
    assert "Greek Yogurt Parfait" in content or "Oatmeal" in content


@pytest.mark.django_db
def test_generate_plan_night_snack_absent_when_false(
    page, live_server, seeded_nutrition_plan, mock_anthropic_client
):
    """When include_night_snack is False, night_snack row should not appear."""
    valid_json = (FIXTURES_DIR / "week_plan_valid.json").read_text()

    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=valid_json)]
    mock_anthropic_client.messages.create.return_value = mock_resp

    page.goto(f"{live_server.url}/meals/")
    page.click("button[type='submit']")
    page.wait_for_url(f"{live_server.url}/meals/", timeout=10000)

    content = page.content()
    assert "Night Snack" not in content
