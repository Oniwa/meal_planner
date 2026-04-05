import datetime

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.nutrition.models import NutritionPlan

from .models import MealPlan, PlannedMeal


def _get_active_nutrition_plan():
    return NutritionPlan.objects.filter(is_active=True).first()


def _get_week_start(date=None):
    if date is None:
        date = datetime.date.today()
    # Monday of the current week
    return date - datetime.timedelta(days=date.weekday())


def meals_current(request):
    nutrition_plan = _get_active_nutrition_plan()
    if not nutrition_plan:
        return redirect("nutrition_import")

    week_start = _get_week_start()
    meal_plan = MealPlan.objects.filter(
        nutrition_plan=nutrition_plan,
        week_start_date=week_start,
        status=MealPlan.STATUS_ACTIVE,
    ).first()

    if not meal_plan:
        return render(
            request,
            "meals/week_plan.html",
            {
                "nutrition_plan": nutrition_plan,
                "meal_plan": None,
                "week_start": week_start,
                "show_generate": True,
            },
        )

    return _render_week_plan(request, meal_plan, nutrition_plan)


def _render_week_plan(request, meal_plan, nutrition_plan):
    planned_meals = meal_plan.planned_meals.select_related("recipe").order_by(
        "day_offset", "meal_slot"
    )

    days = []
    for day_offset in range(7):
        day_date = meal_plan.week_start_date + datetime.timedelta(days=day_offset)
        slots = {}
        for pm in planned_meals:
            if pm.day_offset == day_offset:
                slots[pm.meal_slot] = pm
        days.append({"date": day_date, "day_offset": day_offset, "slots": slots})

    return render(
        request,
        "meals/week_plan.html",
        {
            "nutrition_plan": nutrition_plan,
            "meal_plan": meal_plan,
            "week_start": meal_plan.week_start_date,
            "days": days,
            "show_generate": False,
        },
    )


def generate_plan(request):
    if request.method != "POST":
        return redirect("meals_current")

    nutrition_plan = _get_active_nutrition_plan()
    if not nutrition_plan:
        return redirect("nutrition_import")

    week_start = _get_week_start()

    try:
        from ai.meal_planner_agent import generate_meal_plan

        generate_meal_plan(nutrition_plan, week_start)
    except (ValueError, Exception) as exc:
        return render(
            request,
            "meals/week_plan.html",
            {
                "nutrition_plan": nutrition_plan,
                "meal_plan": None,
                "week_start": week_start,
                "show_generate": True,
                "error": f"Failed to generate meal plan: {exc}",
            },
        )

    return redirect("meals_current")


def week_plan(request, week_start: str):
    try:
        week_start_date = datetime.date.fromisoformat(week_start)
    except ValueError as exc:
        raise Http404("Invalid date format.") from exc

    if week_start_date.weekday() != 0:  # 0 = Monday
        raise Http404("Date must be a Monday.")

    nutrition_plan = _get_active_nutrition_plan()
    if not nutrition_plan:
        return redirect("nutrition_import")

    meal_plan = get_object_or_404(
        MealPlan,
        nutrition_plan=nutrition_plan,
        week_start_date=week_start_date,
        status=MealPlan.STATUS_ACTIVE,
    )

    return _render_week_plan(request, meal_plan, nutrition_plan)


def swap_meal(request):
    if request.method != "POST":
        return redirect("meals_current")

    planned_meal_id = request.POST.get("planned_meal_id")
    reason = request.POST.get("reason", "")

    nutrition_plan = _get_active_nutrition_plan()
    if not nutrition_plan:
        raise Http404("No active nutrition plan.")

    active_plan = MealPlan.objects.filter(
        nutrition_plan=nutrition_plan,
        status=MealPlan.STATUS_ACTIVE,
    ).first()

    if not active_plan:
        raise Http404("No active meal plan.")

    planned_meal = get_object_or_404(
        PlannedMeal,
        pk=planned_meal_id,
        meal_plan=active_plan,
    )

    try:
        from ai.meal_planner_agent import generate_swap

        generate_swap(planned_meal, reason=reason)
        planned_meal.refresh_from_db()

        return render(
            request,
            "meals/partials/meal_cell.html",
            {"pm": planned_meal, "nutrition_plan": nutrition_plan},
        )
    except (ValueError, Exception) as exc:
        return render(
            request,
            "meals/partials/meal_cell_error.html",
            {
                "pm": planned_meal,
                "error": str(exc),
                "nutrition_plan": nutrition_plan,
            },
        )


def meal_detail(request, planned_meal_id: int):
    nutrition_plan = _get_active_nutrition_plan()
    if not nutrition_plan:
        raise Http404("No active nutrition plan.")

    active_plan = MealPlan.objects.filter(
        nutrition_plan=nutrition_plan,
        status=MealPlan.STATUS_ACTIVE,
    ).first()

    if not active_plan:
        raise Http404("No active meal plan.")

    planned_meal = get_object_or_404(
        PlannedMeal,
        pk=planned_meal_id,
        meal_plan=active_plan,
    )

    return render(
        request,
        "meals/meal_detail.html",
        {
            "pm": planned_meal,
            "recipe": planned_meal.recipe,
            "ingredients": planned_meal.recipe.ingredients.all(),
            "nutrition_plan": nutrition_plan,
        },
    )
