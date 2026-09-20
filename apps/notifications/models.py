import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        REPORT_STATUS = "REPORT_STATUS", "Report status"
        GENERAL = "GENERAL", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=500)
    notification_type = models.CharField(max_length=30, choices=Type.choices, default=Type.GENERAL)
    report = models.ForeignKey("reports.Report", on_delete=models.CASCADE, blank=True, null=True, related_name="notifications")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class DeviceInstallation(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "ANDROID", "Android"
        IOS = "IOS", "iOS"
        WEB = "WEB", "Web"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_installations",
    )
    firebase_installation_id = models.CharField(max_length=255, unique=True, db_index=True)
    # FCM token is the FlutterFire-compatible push destination. Never return it through the API.
    # Blank on pre-existing rows until their device logs in and registers again.
    fcm_registration_token = models.CharField(max_length=2048, blank=True, default="")
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.OTHER)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=("user", "is_active"), name="notif_user_active_idx")]

    def __str__(self):
        return f"{self.user_id}:{self.platform}:{self.firebase_installation_id[:12]}"
