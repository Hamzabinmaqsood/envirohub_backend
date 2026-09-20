from django.contrib import admin

from .models import DeviceInstallation, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("title", "message", "user__email")


@admin.register(DeviceInstallation)
class DeviceInstallationAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "is_active", "updated_at")
    list_filter = ("platform", "is_active", "updated_at")
    search_fields = ("user__email", "firebase_installation_id")
    readonly_fields = ("created_at", "updated_at")
