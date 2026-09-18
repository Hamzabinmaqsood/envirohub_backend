from django.urls import path

from . import views

app_name = "authority-dashboard"

urlpatterns = [
    path("login/", views.dashboard_login, name="login"),
    path("logout/", views.dashboard_logout, name="logout"),
    path("", views.overview, name="overview"),
    path("reports/", views.reports_list, name="reports"),
    path("reports/<uuid:report_id>/", views.report_detail, name="report-detail"),
    path("reports/<uuid:report_id>/verify/", views.verify_report, name="verify-report"),
    path("reports/<uuid:report_id>/assign/", views.assign_report, name="assign-report"),
    path("workers/", views.workers_list, name="workers"),
    path("map/", views.report_map, name="map"),
]
