from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name", "name", "phone",
            "profile_picture", "role",
        )
        read_only_fields = ("id", "name", "role")

    def get_name(self, obj):
        return obj.get_full_name().strip() or obj.email


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("id", "email", "password", "name", "first_name", "last_name", "phone")
        read_only_fields = ("id",)

    def validate_email(self, value):
        return value.strip().lower()

    def create(self, validated_data):
        name = validated_data.pop("name", "").strip()
        if name and not validated_data.get("first_name"):
            parts = name.split(maxsplit=1)
            validated_data["first_name"] = parts[0]
            if len(parts) > 1 and not validated_data.get("last_name"):
                validated_data["last_name"] = parts[1]
        password = validated_data.pop("password")
        # Public registration is always a citizen account. Worker/authority
        # accounts are provisioned by an administrator.
        validated_data["role"] = User.Role.CITIZEN
        return User.objects.create_user(password=password, **validated_data)
