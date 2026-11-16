"""Root URL configuration for MindCheck."""

from django.contrib import admin
from django.urls import include, path

from screening import views as screening_views

urlpatterns = [
    path("", screening_views.home, name="home"),
    path("about/", screening_views.about, name="about"),
    path("accounts/", include("accounts.urls")),
    path("screening/", include("screening.urls")),
    path("resources/", include("resources.urls")),
    path("admin/", admin.site.urls),
]

# Custom error pages (shown when DEBUG is False)
handler400 = "mindcheck_project.error_views.bad_request"
handler403 = "mindcheck_project.error_views.permission_denied"
handler404 = "mindcheck_project.error_views.page_not_found"
handler500 = "mindcheck_project.error_views.server_error"
