from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.root_redirect, name="root"),
    path("nutrition/", include("apps.nutrition.urls")),
    path("meals/", include("apps.meals.urls")),
    path("shopping/", include("apps.shopping.urls")),
]
