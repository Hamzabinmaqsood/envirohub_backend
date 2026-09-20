from rest_framework import serializers

from .models import DeviceInstallation, Notification


class NotificationSerializer(serializers.ModelSerializer):
    report_id = serializers.UUIDField(source="report.id", read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ("id", "title", "message", "notification_type", "report_id", "is_read", "created_at")


class DeviceInstallationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceInstallation
        fields = (
            "id",
            "firebase_installation_id",
            "fcm_registration_token",
            "platform",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")
        extra_kwargs = {
            "firebase_installation_id": {"validators": []},
            # The client may submit the token; API list/create responses must not expose it.
            "fcm_registration_token": {"write_only": True, "required": False, "allow_blank": False},
        }

    def create(self, validated_data):
        request = self.context["request"]
        defaults = {
            "user": request.user,
            "platform": validated_data.get("platform", DeviceInstallation.Platform.OTHER),
            "is_active": True,
        }
        # Preserve a previous token if a legacy client sends only the installation ID.
        if "fcm_registration_token" in validated_data:
            defaults["fcm_registration_token"] = validated_data["fcm_registration_token"]
        installation, _ = DeviceInstallation.objects.update_or_create(
            firebase_installation_id=validated_data["firebase_installation_id"],
            defaults=defaults,
        )
        return installation


class DeviceUnregisterSerializer(serializers.Serializer):
    firebase_installation_id = serializers.CharField(max_length=255)
