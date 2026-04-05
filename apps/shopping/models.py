from django.db import models

from apps.meals.models import MealPlan


class ShoppingList(models.Model):
    meal_plan = models.OneToOneField(
        MealPlan, on_delete=models.CASCADE, related_name="shopping_list"
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ShoppingList for {self.meal_plan}"


class ShoppingItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="items")
    ingredient_name = models.CharField(max_length=255)
    total_quantity = models.FloatField()
    unit = models.CharField(max_length=50, blank=True, default="")
    category = models.CharField(max_length=100, blank=True, default="")
    is_checked = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["category", "ingredient_name"]

    def __str__(self):
        return f"{self.total_quantity} {self.unit} {self.ingredient_name}"
