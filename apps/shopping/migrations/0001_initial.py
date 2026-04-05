import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("meals", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShoppingList",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "meal_plan",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shopping_list",
                        to="meals.mealplan",
                    ),
                ),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ShoppingItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "shopping_list",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="shopping.shoppinglist",
                    ),
                ),
                ("ingredient_name", models.CharField(max_length=255)),
                ("total_quantity", models.FloatField()),
                ("unit", models.CharField(blank=True, default="", max_length=50)),
                ("category", models.CharField(blank=True, default="", max_length=100)),
                ("is_checked", models.BooleanField(default=False)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
            ],
            options={
                "ordering": ["category", "ingredient_name"],
            },
        ),
    ]
