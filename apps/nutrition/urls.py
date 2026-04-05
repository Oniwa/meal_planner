from django.urls import path

from . import views

urlpatterns = [
    path("import/", views.import_plan, name="nutrition_import"),
    path("plan/", views.plan_summary, name="nutrition_plan"),
]
