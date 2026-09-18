from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsAuthority, IsCitizen, IsWorker

from .models import Category, Report, ReportImage
from .serializers import (
    AssignWorkerSerializer,
    AuthorityReportDetailSerializer,
    CategorySerializer,
    ReportCreateSerializer,
    ReportDetailSerializer,
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
        return report_queryset().filter(citizen=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return ReportCreateSerializer
        if self.action == "retrieve":
            return ReportDetailSerializer
        return ReportListSerializer

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
