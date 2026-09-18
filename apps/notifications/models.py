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
