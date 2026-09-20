from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DeviceInstallation, Notification
from .serializers import (
    DeviceInstallationSerializer,
    DeviceUnregisterSerializer,
    NotificationSerializer,
)


@extend_schema_view(list=extend_schema(tags=["Notifications"]))
class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related("report")

    @extend_schema(tags=["Notifications"], request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["patch"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)

    @extend_schema(tags=["Notifications"], request=None)
    @action(detail=False, methods=["patch"], url_path="read-all")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})


@extend_schema_view(
    list=extend_schema(tags=["Push Notifications"]),
    create=extend_schema(tags=["Push Notifications"]),
    destroy=extend_schema(tags=["Push Notifications"]),
)
class DeviceInstallationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DeviceInstallationSerializer

    def get_queryset(self):
        return DeviceInstallation.objects.filter(user=self.request.user)

    @extend_schema(tags=["Push Notifications"], request=DeviceUnregisterSerializer)
    @action(detail=False, methods=["post"], url_path="unregister")
    def unregister(self, request):
        serializer = DeviceUnregisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = DeviceInstallation.objects.filter(
            user=request.user,
            firebase_installation_id=serializer.validated_data["firebase_installation_id"],
            is_active=True,
        ).update(is_active=False)
        return Response({"updated": updated}, status=status.HTTP_200_OK)
