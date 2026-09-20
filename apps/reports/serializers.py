from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import create_notification

from .models import Category, Report, ReportImage, ReportStatusHistory
from .validators import validate_report_image

UserModel = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")


class PublicUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = UserModel
        fields = ("id", "name")

    def get_name(self, obj):
        return obj.get_full_name().strip() or obj.email


class WorkerDirectorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = UserModel
        fields = ("id", "name", "email", "phone", "is_active")

    def get_name(self, obj):
        return obj.get_full_name().strip() or obj.email


class ReportImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportImage
        fields = ("id", "image", "image_type", "created_at")


class StatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ReportStatusHistory
        fields = ("id", "status", "note", "changed_by_name", "created_at")

    def get_changed_by_name(self, obj):
        if not obj.changed_by:
            return None
        return obj.changed_by.get_full_name().strip() or obj.changed_by.email


class ReportListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            "id", "category", "description", "status", "address",
            "latitude", "longitude", "thumbnail", "created_at", "updated_at",
        )

    def get_latitude(self, obj):
        return obj.location.y

    def get_longitude(self, obj):
        return obj.location.x

    def get_thumbnail(self, obj):
        image = next((i for i in obj.images.all() if i.image_type == ReportImage.ImageType.BEFORE), None)
        if not image:
            return None
        request = self.context.get("request")
        url = image.image.url
        return request.build_absolute_uri(url) if request else url


class NearbyReportQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius_m = serializers.IntegerField(min_value=50, max_value=2000, default=200, required=False)
    category = serializers.SlugField(required=False, allow_blank=True)


class NearbyReportSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    distance_m = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = ("id", "category", "status", "distance_m", "created_at")

    def get_distance_m(self, obj):
        distance = getattr(obj, "distance", None)
        if distance is None:
            return None
        return round(distance.m)


class ReportDetailSerializer(ReportListSerializer):
    images = ReportImageSerializer(many=True, read_only=True)
    timeline = StatusHistorySerializer(source="status_history", many=True, read_only=True)
    assigned_worker = PublicUserSerializer(read_only=True)

    class Meta(ReportListSerializer.Meta):
        fields = ReportListSerializer.Meta.fields + (
            "images", "timeline", "assigned_worker",
            "verified_at", "assigned_at", "started_at", "resolved_at",
        )


class AuthorityReportDetailSerializer(ReportDetailSerializer):
    citizen = PublicUserSerializer(read_only=True)
    verified_by = PublicUserSerializer(read_only=True)

    class Meta(ReportDetailSerializer.Meta):
        fields = ReportDetailSerializer.Meta.fields + ("citizen", "verified_by")


class ReportCreateSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field="slug", queryset=Category.objects.filter(is_active=True)
    )
    latitude = serializers.FloatField(write_only=True, min_value=-90, max_value=90)
    longitude = serializers.FloatField(write_only=True, min_value=-180, max_value=180)
    images = serializers.ListField(
        child=serializers.ImageField(validators=[validate_report_image]),
        write_only=True, min_length=1, max_length=5,
    )

    class Meta:
        model = Report
        fields = ("id", "category", "description", "address", "latitude", "longitude", "images")
        read_only_fields = ("id",)

    @transaction.atomic
    def create(self, validated_data):
        images = validated_data.pop("images")
        latitude = validated_data.pop("latitude")
        longitude = validated_data.pop("longitude")
        request = self.context["request"]

        report = Report.objects.create(
            citizen=request.user,
            location=Point(longitude, latitude, srid=4326),
            **validated_data,
        )

        for image in images:
            ReportImage.objects.create(
                report=report,
                image=image,
                image_type=ReportImage.ImageType.BEFORE,
                uploaded_by=request.user,
            )
        ReportStatusHistory.objects.create(
            report=report,
            status=Report.Status.SUBMITTED,
            changed_by=request.user,
            note="Report submitted by citizen.",
        )
        create_notification(
            user=request.user,
            title="Report submitted",
            message="Your environmental report has been submitted successfully.",
            notification_type=Notification.Type.REPORT_STATUS,
            report=report,
        )
        return report

    def to_representation(self, instance):
        return ReportDetailSerializer(instance, context=self.context).data


class WorkflowNoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class AssignWorkerSerializer(WorkflowNoteSerializer):
    worker_id = serializers.PrimaryKeyRelatedField(
        source="worker",
        queryset=UserModel.objects.filter(role=User.Role.WORKER, is_active=True),
    )


class ResolveReportSerializer(WorkflowNoteSerializer):
    images = serializers.ListField(
        child=serializers.ImageField(validators=[validate_report_image]),
        write_only=True,
        min_length=1,
        max_length=5,
    )
