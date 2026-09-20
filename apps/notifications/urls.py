from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceInstallationViewSet, NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")
router.register("notification-devices", DeviceInstallationViewSet, basename="notification-device")

urlpatterns = [path("", include(router.urls))]
