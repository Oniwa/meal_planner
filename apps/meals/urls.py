from django.urls import path

from . import views

urlpatterns = [
    path("", views.meals_current, name="meals_current"),
    path("generate/", views.generate_plan, name="meals_generate"),
    path("swap/", views.swap_meal, name="meals_swap"),
    path("meal/<int:planned_meal_id>/", views.meal_detail, name="meal_detail"),
    path("<str:week_start>/", views.week_plan, name="meals_week"),
]
