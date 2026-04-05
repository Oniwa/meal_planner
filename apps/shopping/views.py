from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.meals.models import MealPlan
from apps.nutrition.models import NutritionPlan

from .models import ShoppingItem, ShoppingList


def shopping_list(request):
    nutrition_plan = NutritionPlan.objects.filter(is_active=True).first()
    if not nutrition_plan:
        from django.shortcuts import redirect

        return redirect("nutrition_import")

    active_plan = MealPlan.objects.filter(
        nutrition_plan=nutrition_plan,
        status=MealPlan.STATUS_ACTIVE,
    ).first()

    if not active_plan:
        return render(request, "shopping/list.html", {"items_by_category": {}, "meal_plan": None})

    try:
        sl = active_plan.shopping_list
    except ShoppingList.DoesNotExist:
        return render(
            request, "shopping/list.html", {"items_by_category": {}, "meal_plan": active_plan}
        )

    items = sl.items.all().order_by("category", "ingredient_name")
    items_by_category = {}
    for item in items:
        category = item.category or "other"
        if category not in items_by_category:
            items_by_category[category] = []
        items_by_category[category].append(item)

    return render(
        request,
        "shopping/list.html",
        {
            "items_by_category": items_by_category,
            "meal_plan": active_plan,
        },
    )


def toggle_check(request):
    if request.method != "POST":
        raise Http404("POST required.")

    item_id = request.POST.get("item_id")
    item = get_object_or_404(ShoppingItem, pk=item_id)
    item.is_checked = not item.is_checked
    item.save()

    return render(request, "shopping/partials/item_row.html", {"item": item})
