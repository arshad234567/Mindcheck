from django.urls import path

from . import views

app_name = "screening"

urlpatterns = [
    path("", views.tool_list, name="tools"),
    path("consent/", views.consent, name="consent"),
    path("take/<slug:slug>/", views.take_screening, name="take"),
    path("support/", views.crisis, name="crisis"),
    path("result/<int:pk>/", views.result, name="result"),
    path("result/private/", views.session_result, name="session_result"),
    path("result/private/clear/", views.clear_session_result, name="clear_session_result"),
    path("history/", views.history, name="history"),
    path("history/<int:pk>/delete/", views.delete_assessment, name="delete_assessment"),
    path("counsellor/", views.counsellor_dashboard, name="counsellor"),
    path("counsellor/guidance/<str:tier>/edit/", views.edit_guidance, name="edit_guidance"),
]
