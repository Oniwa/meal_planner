import json

from django.shortcuts import redirect, render

from .models import NutritionPlan
from .validators import validate_and_clean


def import_plan(request):
    if request.method == "POST":
        raw = request.POST.get("json_data", "").strip()

        # Handle file upload
        if not raw and "json_file" in request.FILES:
            try:
                raw = request.FILES["json_file"].read().decode("utf-8")
            except Exception:
                return render(
                    request,
                    "nutrition/import.html",
                    {"error": "Could not read uploaded file."},
                )

        if not raw:
            return render(
                request,
                "nutrition/import.html",
                {"error": "Please paste JSON or upload a file."},
            )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return render(
                request,
                "nutrition/import.html",
                {"error": f"Invalid JSON: {exc}", "json_data": raw},
            )

        try:
            cleaned = validate_and_clean(data)
        except ValueError as exc:
            return render(
                request,
                "nutrition/import.html",
                {"error": str(exc), "json_data": raw},
            )

        # Deactivate previous active plan
        NutritionPlan.objects.filter(is_active=True).update(is_active=False)

        NutritionPlan.objects.create(**cleaned)
        return redirect("nutrition_plan")

    return render(request, "nutrition/import.html", {})


def plan_summary(request):
    plan = NutritionPlan.objects.filter(is_active=True).first()
    if not plan:
        return redirect("nutrition_import")
    return render(request, "nutrition/plan_summary.html", {"plan": plan})
