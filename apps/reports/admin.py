from django.contrib import admin

from .models import Category, Report, ReportImage, ReportStatusHistory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}


class ReportImageInline(admin.TabularInline):
    model = ReportImage
    extra = 0
    readonly_fields = ("image_type", "uploaded_by", "created_at")


class StatusHistoryInline(admin.TabularInline):
    model = ReportStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("status", "changed_by", "note", "created_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id", "category", "citizen", "status", "assigned_worker", "created_at"
    )
    list_filter = ("status", "category", "created_at")
    search_fields = (
        "id", "citizen__email", "assigned_worker__email", "description", "address"
    )
    readonly_fields = (
        "status",
        "verified_by",
        "assigned_worker",
        "created_at",
        "updated_at",
        "verified_at",
        "assigned_at",
        "started_at",
        "resolved_at",
    )
    inlines = (ReportImageInline, StatusHistoryInline)
