from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuthorityReportViewSet,
    AuthorityWorkerListAPIView,
    CategoryListAPIView,
    ReportViewSet,
    WorkerReportViewSet,
)

citizen_router = DefaultRouter()
citizen_router.register("reports", ReportViewSet, basename="report")

authority_router = DefaultRouter()
authority_router.register("reports", AuthorityReportViewSet, basename="authority-report")

worker_router = DefaultRouter()
worker_router.register("reports", WorkerReportViewSet, basename="worker-report")

urlpatterns = [
    path("categories/", CategoryListAPIView.as_view(), name="category-list"),
    path("authority/workers/", AuthorityWorkerListAPIView.as_view(), name="authority-worker-list"),
    path("authority/", include(authority_router.urls)),
    path("worker/", include(worker_router.urls)),
    path("", include(citizen_router.urls)),
]
