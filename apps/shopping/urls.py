from django.urls import path

from . import views

urlpatterns = [
    path("", views.shopping_list, name="shopping_list"),
    path("check/", views.toggle_check, name="shopping_check"),
]
