from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    path("", views.resource_list, name="list"),
    path("category/<slug:category_slug>/", views.resource_list, name="by_category"),
    path("<int:pk>/", views.resource_detail, name="detail"),
    path("add/", views.resource_create, name="create"),
    path("<int:pk>/edit/", views.resource_update, name="update"),
    path("<int:pk>/delete/", views.resource_delete, name="delete"),
]
