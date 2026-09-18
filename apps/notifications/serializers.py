from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    report_id = serializers.UUIDField(source="report.id", read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ("id", "title", "message", "notification_type", "report_id", "is_read", "created_at")
