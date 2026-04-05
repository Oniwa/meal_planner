from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def sample_nutrition_plan(db):
    from apps.nutrition.models import NutritionPlan

    return NutritionPlan.objects.create(
        label="Test Plan - April 2026",
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


@pytest.fixture
def sample_nutrition_plan_with_night_snack(db):
    from apps.nutrition.models import NutritionPlan

    return NutritionPlan.objects.create(
        label="Test Plan With Night Snack",
        is_active=True,
        daily_calories=2000,
        protein_grams=150,
        carbs_grams=200,
        fat_grams=65,
        max_cook_time_minutes=45,
        cooking_skill_level="intermediate",
        meal_variety="medium",
        include_night_snack=True,
    )


@pytest.fixture
def mock_anthropic_client(request):
    """
    Function-scoped, opt-in mock for the Anthropic client.
    Tests must explicitly request this fixture.
    Returns the mock client so tests can configure side_effect / return_value.
    """
    valid_plan_json = _load_fixture("week_plan_valid.json")

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=valid_plan_json)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("ai.client.get_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def valid_plan_json() -> str:
    return _load_fixture("week_plan_valid.json")


@pytest.fixture
def invalid_json_txt() -> str:
    return _load_fixture("week_plan_invalid_json.txt")


@pytest.fixture
def bad_nutrition_json() -> str:
    return _load_fixture("week_plan_bad_nutrition.json")


@pytest.fixture
def swap_response_json() -> str:
    return _load_fixture("swap_response.json")
