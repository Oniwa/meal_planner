import pytest

from apps.nutrition.validators import validate_and_clean

VALID_DATA = {
    "label": "John - April 2026",
    "daily_calories": 2000,
    "protein_grams": 150,
    "carbs_grams": 200,
    "fat_grams": 65,
    "max_cook_time_minutes": 45,
    "cooking_skill_level": "intermediate",
    "meal_variety": "medium",
    "include_night_snack": False,
}


def test_valid_json_no_errors():
    result = validate_and_clean(VALID_DATA)
    assert result["label"] == "John - April 2026"
    assert result["daily_calories"] == 2000


def test_missing_required_field_raises():
    data = dict(VALID_DATA)
    del data["label"]
    with pytest.raises(ValueError, match="label"):
        validate_and_clean(data)


def test_missing_daily_calories_raises():
    data = dict(VALID_DATA)
    del data["daily_calories"]
    with pytest.raises(ValueError, match="daily_calories"):
        validate_and_clean(data)


def test_missing_protein_grams_raises():
    data = dict(VALID_DATA)
    del data["protein_grams"]
    with pytest.raises(ValueError, match="protein_grams"):
        validate_and_clean(data)


def test_missing_carbs_grams_raises():
    data = dict(VALID_DATA)
    del data["carbs_grams"]
    with pytest.raises(ValueError, match="carbs_grams"):
        validate_and_clean(data)


def test_missing_fat_grams_raises():
    data = dict(VALID_DATA)
    del data["fat_grams"]
    with pytest.raises(ValueError, match="fat_grams"):
        validate_and_clean(data)


def test_missing_max_cook_time_raises():
    data = dict(VALID_DATA)
    del data["max_cook_time_minutes"]
    with pytest.raises(ValueError, match="max_cook_time_minutes"):
        validate_and_clean(data)


def test_missing_cooking_skill_level_raises():
    data = dict(VALID_DATA)
    del data["cooking_skill_level"]
    with pytest.raises(ValueError, match="cooking_skill_level"):
        validate_and_clean(data)


def test_missing_meal_variety_raises():
    data = dict(VALID_DATA)
    del data["meal_variety"]
    with pytest.raises(ValueError, match="meal_variety"):
        validate_and_clean(data)


def test_missing_include_night_snack_raises():
    data = dict(VALID_DATA)
    del data["include_night_snack"]
    with pytest.raises(ValueError, match="include_night_snack"):
        validate_and_clean(data)


def test_wrong_type_daily_calories_raises():
    data = dict(VALID_DATA)
    data["daily_calories"] = "two thousand"
    with pytest.raises(ValueError, match="daily_calories"):
        validate_and_clean(data)


def test_wrong_type_label_raises():
    data = dict(VALID_DATA)
    data["label"] = 12345
    with pytest.raises(ValueError, match="label"):
        validate_and_clean(data)


def test_wrong_type_include_night_snack_raises():
    data = dict(VALID_DATA)
    data["include_night_snack"] = "yes"
    with pytest.raises(ValueError, match="include_night_snack"):
        validate_and_clean(data)


def test_extra_unknown_fields_accepted():
    data = dict(VALID_DATA)
    data["unknown_field"] = "ignored"
    data["another_unknown"] = 42
    result = validate_and_clean(data)
    assert "unknown_field" not in result
    assert result["daily_calories"] == 2000


def test_optional_fields_absent_use_defaults():
    result = validate_and_clean(VALID_DATA)
    assert result["heart_healthy"] is False
    assert result["is_vegetarian"] is False
    assert result["allergies"] == []
    assert result["notes"] == ""
    assert result["meal_prep_friendly"] is False


def test_optional_fields_present_are_used():
    data = dict(VALID_DATA)
    data["heart_healthy"] = True
    data["allergies"] = ["peanuts"]
    data["notes"] = "Prefers Mediterranean"
    result = validate_and_clean(data)
    assert result["heart_healthy"] is True
    assert result["allergies"] == ["peanuts"]
    assert result["notes"] == "Prefers Mediterranean"
