from django.shortcuts import redirect


def root_redirect(request):
    from apps.nutrition.models import NutritionPlan

    if NutritionPlan.objects.filter(is_active=True).exists():
        return redirect("meals_current")
    return redirect("nutrition_import")
