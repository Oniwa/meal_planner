from django.db import models

from apps.nutrition.models import NutritionPlan


class Recipe(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    instructions = models.TextField(blank=True, default="")
    prep_time_minutes = models.IntegerField(default=0)
    cook_time_minutes = models.IntegerField(default=0)
    servings = models.IntegerField(default=1)
    meal_type = models.CharField(max_length=50, blank=True, default="")
    cuisine_type = models.CharField(max_length=100, blank=True, default="")

    # Nutrition per serving
    calories = models.IntegerField(default=0)
    protein_grams = models.FloatField(default=0.0)
    carbs_grams = models.FloatField(default=0.0)
    fat_grams = models.FloatField(default=0.0)
    fiber_grams = models.FloatField(null=True, blank=True)
    sodium_mg = models.FloatField(null=True, blank=True)

    tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    name = models.CharField(max_length=255)
    quantity = models.FloatField()
    unit = models.CharField(max_length=50, blank=True, default="")
    notes = models.CharField(max_length=255, blank=True, default="")
    category = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.name}"


class MealPlan(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    nutrition_plan = models.ForeignKey(NutritionPlan, on_delete=models.CASCADE)
    week_start_date = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"MealPlan {self.week_start_date} ({self.status})"


class PlannedMeal(models.Model):
    SLOT_CHOICES = [
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("dinner", "Dinner"),
        ("afternoon_snack", "Afternoon Snack"),
        ("night_snack", "Night Snack"),
    ]

    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name="planned_meals")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    day_offset = models.IntegerField()  # 0=Monday ... 6=Sunday
    meal_slot = models.CharField(max_length=20, choices=SLOT_CHOICES)
    is_optional = models.BooleanField(default=False)
    was_swapped = models.BooleanField(default=False)
    swap_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["day_offset", "meal_slot"]
        unique_together = [("meal_plan", "day_offset", "meal_slot")]

    def __str__(self):
        return f"{self.meal_plan} Day {self.day_offset} {self.meal_slot}: {self.recipe}"
