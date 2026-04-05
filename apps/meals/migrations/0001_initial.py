import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("nutrition", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Recipe",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("instructions", models.TextField(blank=True, default="")),
                ("prep_time_minutes", models.IntegerField(default=0)),
                ("cook_time_minutes", models.IntegerField(default=0)),
                ("servings", models.IntegerField(default=1)),
                ("meal_type", models.CharField(blank=True, default="", max_length=50)),
                ("cuisine_type", models.CharField(blank=True, default="", max_length=100)),
                ("calories", models.IntegerField(default=0)),
                ("protein_grams", models.FloatField(default=0.0)),
                ("carbs_grams", models.FloatField(default=0.0)),
                ("fat_grams", models.FloatField(default=0.0)),
                ("fiber_grams", models.FloatField(blank=True, null=True)),
                ("sodium_mg", models.FloatField(blank=True, null=True)),
                ("tags", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Ingredient",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingredients",
                        to="meals.recipe",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("quantity", models.FloatField()),
                ("unit", models.CharField(blank=True, default="", max_length=50)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("category", models.CharField(blank=True, default="", max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="MealPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "nutrition_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="nutrition.nutritionplan"
                    ),
                ),
                ("week_start_date", models.DateField()),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("archived", "Archived")],
                        default="active",
                        max_length=20,
                    ),
                ),
            ],
            options={
                "ordering": ["-generated_at"],
            },
        ),
        migrations.CreateModel(
            name="PlannedMeal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "meal_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="planned_meals",
                        to="meals.mealplan",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="meals.recipe"
                    ),
                ),
                ("day_offset", models.IntegerField()),
                (
                    "meal_slot",
                    models.CharField(
                        choices=[
                            ("breakfast", "Breakfast"),
                            ("lunch", "Lunch"),
                            ("dinner", "Dinner"),
                            ("afternoon_snack", "Afternoon Snack"),
                            ("night_snack", "Night Snack"),
                        ],
                        max_length=20,
                    ),
                ),
                ("is_optional", models.BooleanField(default=False)),
                ("was_swapped", models.BooleanField(default=False)),
                ("swap_reason", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ["day_offset", "meal_slot"],
                "unique_together": {("meal_plan", "day_offset", "meal_slot")},
            },
        ),
    ]
