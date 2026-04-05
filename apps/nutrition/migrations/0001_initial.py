from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="NutritionPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("label", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                ("daily_calories", models.IntegerField()),
                ("protein_grams", models.IntegerField()),
                ("carbs_grams", models.IntegerField()),
                ("fat_grams", models.IntegerField()),
                ("heart_healthy", models.BooleanField(default=False)),
                ("low_sodium", models.BooleanField(default=False)),
                ("low_sugar", models.BooleanField(default=False)),
                ("diabetic_friendly", models.BooleanField(default=False)),
                ("anti_inflammatory", models.BooleanField(default=False)),
                ("is_vegetarian", models.BooleanField(default=False)),
                ("is_vegan", models.BooleanField(default=False)),
                ("is_gluten_free", models.BooleanField(default=False)),
                ("is_dairy_free", models.BooleanField(default=False)),
                ("allergies", models.JSONField(default=list)),
                ("disliked_foods", models.JSONField(default=list)),
                ("liked_foods", models.JSONField(default=list)),
                ("preferred_cuisines", models.JSONField(default=list)),
                ("max_cook_time_minutes", models.IntegerField()),
                ("meal_prep_friendly", models.BooleanField(default=False)),
                ("cooking_skill_level", models.CharField(max_length=50)),
                ("meal_variety", models.CharField(max_length=50)),
                ("include_night_snack", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
