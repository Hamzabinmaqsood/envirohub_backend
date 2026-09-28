from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsAuthority, IsCitizen, IsWorker

from .models import Category, Report, ReportImage, ReportConfirmation, ReportFollow
from .serializers import (
    AssignWorkerSerializer,
    AuthorityReportDetailSerializer,
    CategorySerializer,
    CommunityNearbyReportSerializer,
    CommunityReportSerializer,
    NearbyReportQuerySerializer,
    ReportCreateSerializer,
    OwnCommunityReportSerializer,
    ReportListSerializer,
    ResolveReportSerializer,
    StatusHistorySerializer,
    WorkerDirectorySerializer,
    WorkflowNoteSerializer,
)
from .services import ReportWorkflow


def report_queryset():
    return (
        Report.objects.select_related(
            "category", "citizen", "assigned_worker", "verified_by"
        )
        .prefetch_related(
            Prefetch("images", queryset=ReportImage.objects.order_by("created_at")),
            "status_history__changed_by",
        )
    )


def community_queryset(user):
    """Count distinct users, plus this citizen's independent engagement states."""
    from .models import ReportConfirmation, ReportFollow

    return report_queryset().annotate(
        confirmation_count=Count("confirmations", distinct=True),
        follower_count=Count("followers", distinct=True),
        is_confirmed=Exists(
            ReportConfirmation.objects.filter(report_id=OuterRef("pk"), user=user)
        ),
        is_following=Exists(
            ReportFollow.objects.filter(report_id=OuterRef("pk"), user=user)
        ),
    )


@extend_schema(tags=["Categories"])
class CategoryListAPIView(generics.ListAPIView):
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(is_active=True)


@extend_schema_view(
    list=extend_schema(tags=["Citizen Reports"]),
    create=extend_schema(tags=["Citizen Reports"]),
    retrieve=extend_schema(tags=["Citizen Reports"]),
)
class ReportViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsCitizen]
    filterset_fields = ("status", "category__slug")
    ordering_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return community_queryset(self.request.user).filter(citizen=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return ReportCreateSerializer
        if self.action == "retrieve":
            return OwnCommunityReportSerializer
        return ReportListSerializer


    def _community_report(self):
        """Shared report access without broadening the private /reports/{id}/ endpoint."""
        qs = community_queryset(self.request.user).filter(
            Q(citizen=self.request.user) | ~Q(status=Report.Status.REJECTED)
        )
        report = get_object_or_404(qs, pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, report)
        return report

    def _community_response(self, report_id):
        report = community_queryset(self.request.user).get(pk=report_id)
        return Response(CommunityReportSerializer(report, context=self.get_serializer_context()).data)

    @extend_schema(tags=["Community"], responses=CommunityReportSerializer)
    @action(detail=True, methods=["get"], url_path="community")
    def community(self, request, pk=None):
        return Response(
            CommunityReportSerializer(
                self._community_report(), context=self.get_serializer_context()
            ).data
        )

    @extend_schema(tags=["Community"], request=None, responses=CommunityReportSerializer)
    @action(detail=True, methods=["post", "delete"], url_path="confirm")
    def confirm(self, request, pk=None):
        report = self._community_report()
        if report.citizen_id == request.user.id:
            return Response({"detail": "You cannot confirm your own report."}, status=400)
        if request.method == "POST":
            with transaction.atomic():
                # Lock only the Report row, not nullable worker/verification joins.
                locked = Report.objects.select_for_update().get(pk=report.pk)
                if locked.status in (Report.Status.RESOLVED, Report.Status.REJECTED):
                    return Response({"detail": "This report is closed to new confirmations."}, status=400)
                ReportConfirmation.objects.get_or_create(report=locked, user=request.user)
        else:
            ReportConfirmation.objects.filter(report=report, user=request.user).delete()
        return self._community_response(report.pk)

    @extend_schema(tags=["Community"], request=None, responses=CommunityReportSerializer)
    @action(detail=True, methods=["post", "delete"], url_path="follow")
    def follow(self, request, pk=None):
        report = self._community_report()
        if report.citizen_id == request.user.id:
            return Response({"detail": "Your own report already sends you updates."}, status=400)
        if request.method == "POST":
            with transaction.atomic():
                # Lock only the Report row, not nullable worker/verification joins.
                locked = Report.objects.select_for_update().get(pk=report.pk)
                if locked.status in (Report.Status.RESOLVED, Report.Status.REJECTED):
                    return Response({"detail": "This report is closed to new followers."}, status=400)
                ReportFollow.objects.get_or_create(report=locked, user=request.user)
        else:
            ReportFollow.objects.filter(report=report, user=request.user).delete()
        return self._community_response(report.pk)

    @extend_schema(tags=["Community"], responses=CommunityReportSerializer(many=True))
    @action(detail=False, methods=["get"], url_path="following")
    def following(self, request):
        qs = community_queryset(request.user).filter(
            is_following=True
        ).exclude(status=Report.Status.REJECTED).order_by("-created_at")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = CommunityReportSerializer(
                page, many=True, context=self.get_serializer_context()
            )
            return self.get_paginated_response(serializer.data)
        return Response(
            CommunityReportSerializer(qs, many=True, context=self.get_serializer_context()).data
        )

    @extend_schema(
        tags=["Citizen Reports"],
        parameters=[NearbyReportQuerySerializer],
        responses=CommunityNearbyReportSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="nearby")
    def nearby(self, request):
        query = NearbyReportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        latitude = query.validated_data["latitude"]
        longitude = query.validated_data["longitude"]
        radius_m = query.validated_data.get("radius_m", 200)
        category_slug = query.validated_data.get("category", "")

        origin = Point(longitude, latitude, srid=4326)
        nearby_reports = (
            community_queryset(request.user)
            .exclude(status__in=[Report.Status.RESOLVED, Report.Status.REJECTED])
            .filter(location__distance_lte=(origin, D(m=radius_m)))
            .annotate(distance=Distance("location", origin))
            .order_by("distance", "-created_at")
        )
        if category_slug:
            nearby_reports = nearby_reports.filter(category__slug=category_slug)

        serializer = CommunityNearbyReportSerializer(nearby_reports[:10], many=True)
        return Response(serializer.data)

    @extend_schema(tags=["Citizen Reports"], responses=StatusHistorySerializer(many=True))
    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        report = self.get_object()
        serializer = StatusHistorySerializer(
            report.status_history.select_related("changed_by"), many=True
        )
        return Response(serializer.data)


@extend_schema(tags=["Authority"])
class AuthorityWorkerListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthority]
    serializer_class = WorkerDirectorySerializer
    pagination_class = None

    def get_queryset(self):
        return User.objects.filter(role=User.Role.WORKER, is_active=True).order_by("first_name", "email")


@extend_schema_view(
    list=extend_schema(tags=["Authority"]),
    retrieve=extend_schema(tags=["Authority"]),
)
class AuthorityReportViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthority]
    serializer_class = AuthorityReportDetailSerializer
    filterset_fields = ("status", "category__slug", "assigned_worker")
    ordering_fields = ("created_at", "updated_at", "verified_at", "assigned_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        return report_queryset()

    @extend_schema(
        tags=["Authority"],
        request=WorkflowNoteSerializer,
        responses=AuthorityReportDetailSerializer,
    )
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        self.get_object()  # object-level existence check within authority queryset
        payload = WorkflowNoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        report = ReportWorkflow.verify(pk, request.user, payload.validated_data.get("note", ""))
        return Response(self.get_serializer(report).data)

    @extend_schema(
        tags=["Authority"],
        request=AssignWorkerSerializer,
        responses=AuthorityReportDetailSerializer,
    )
    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, pk=None):
        self.get_object()
        payload = AssignWorkerSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        report = ReportWorkflow.assign(
            pk,
            request.user,
            payload.validated_data["worker"],
            payload.validated_data.get("note", ""),
        )
        return Response(self.get_serializer(report).data)


@extend_schema_view(
    list=extend_schema(tags=["Worker"]),
    retrieve=extend_schema(tags=["Worker"]),
)
class WorkerReportViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsWorker]
    serializer_class = AuthorityReportDetailSerializer
    filterset_fields = ("status", "category__slug")
    ordering_fields = ("created_at", "assigned_at", "started_at")
    ordering = ("-assigned_at", "-created_at")

    def get_queryset(self):
        return report_queryset().filter(assigned_worker=self.request.user)

    @extend_schema(
        tags=["Worker"],
        request=WorkflowNoteSerializer,
        responses=AuthorityReportDetailSerializer,
    )
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        self.get_object()
        payload = WorkflowNoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        report = ReportWorkflow.start(pk, request.user, payload.validated_data.get("note", ""))
        return Response(self.get_serializer(report).data)

    @extend_schema(
        tags=["Worker"],
        request=ResolveReportSerializer,
        responses=AuthorityReportDetailSerializer,
    )
    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        self.get_object()
        payload = ResolveReportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        report = ReportWorkflow.resolve(
            pk,
            request.user,
            payload.validated_data["images"],
            payload.validated_data.get("note", ""),
        )
        return Response(self.get_serializer(report).data)
