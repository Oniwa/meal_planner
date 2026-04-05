REQUIRED_FIELDS = {
    "label": str,
    "daily_calories": (int, float),
    "protein_grams": (int, float),
    "carbs_grams": (int, float),
    "fat_grams": (int, float),
    "max_cook_time_minutes": (int, float),
    "cooking_skill_level": str,
    "meal_variety": str,
    "include_night_snack": bool,
}

OPTIONAL_DEFAULTS = {
    "heart_healthy": False,
    "low_sodium": False,
    "low_sugar": False,
    "diabetic_friendly": False,
    "anti_inflammatory": False,
    "is_vegetarian": False,
    "is_vegan": False,
    "is_gluten_free": False,
    "is_dairy_free": False,
    "allergies": list,
    "disliked_foods": list,
    "liked_foods": list,
    "preferred_cuisines": list,
    "meal_prep_friendly": False,
    "notes": "",
}

# Fields to ignore from input (not model fields)
IGNORED_FIELDS = {"name"}


def validate_and_clean(data: dict) -> dict:
    """
    Validate required fields and apply defaults for optional ones.
    Returns cleaned dict suitable for NutritionPlan creation.
    Raises ValueError with field name if validation fails.
    """
    cleaned = {}

    # Validate required fields
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            raise ValueError(f"Missing required field: '{field}'")
        value = data[field]
        if not isinstance(value, expected_type):
            if isinstance(expected_type, tuple):
                type_names = " or ".join(t.__name__ for t in expected_type)
            else:
                type_names = expected_type.__name__
            raise ValueError(f"Field '{field}' must be {type_names}, got {type(value).__name__}")
        # Coerce float to int for integer fields
        if field in (
            "daily_calories",
            "protein_grams",
            "carbs_grams",
            "fat_grams",
            "max_cook_time_minutes",
        ):
            cleaned[field] = int(value)
        else:
            cleaned[field] = value

    # Apply optional fields with defaults
    for field, default in OPTIONAL_DEFAULTS.items():
        if field in data:
            cleaned[field] = data[field]
        elif callable(default):
            cleaned[field] = default()
        else:
            cleaned[field] = default

    return cleaned
