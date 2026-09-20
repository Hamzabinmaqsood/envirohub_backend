from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import create_notification

from .models import Report, ReportImage, ReportStatusHistory


class ReportWorkflow:
    """Atomic state transitions for authority/worker actions."""

    @staticmethod
    def _locked(report_id):
        # Lock only the Report row. Nullable select_related() joins such as
        # assigned_worker/verified_by become LEFT OUTER JOINs, and PostgreSQL
        # does not allow SELECT ... FOR UPDATE on the nullable side of an outer join.
        # Non-null citizen/category relations are safe to join here.
        return (
            Report.objects.select_for_update()
            .select_related("citizen", "category")
            .get(pk=report_id)
        )

    @staticmethod
    def _history(report, actor, note):
        ReportStatusHistory.objects.create(
            report=report,
            status=report.status,
            changed_by=actor,
            note=note,
        )

    @staticmethod
    def _notify(report, title, message):
        create_notification(
            user=report.citizen,
            title=title,
            message=message,
            notification_type=Notification.Type.REPORT_STATUS,
            report=report,
        )

    @classmethod
    @transaction.atomic
    def verify(cls, report_id, actor, note=""):
        report = cls._locked(report_id)
        if report.status not in {Report.Status.SUBMITTED, Report.Status.REOPENED}:
            raise serializers.ValidationError(
                {"status": f"Only SUBMITTED or REOPENED reports can be verified; current status is {report.status}."}
            )

        report.status = Report.Status.VERIFIED
        report.verified_by = actor
        report.verified_at = timezone.now()
        report.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])

        cls._history(report, actor, note or "Report verified by authority.")
        cls._notify(
            report,
            "Report verified",
            "Your environmental report has been verified by the responsible authority.",
        )
        return report

    @classmethod
    @transaction.atomic
    def assign(cls, report_id, actor, worker, note=""):
        report = cls._locked(report_id)
        if report.status != Report.Status.VERIFIED:
            raise serializers.ValidationError(
                {"status": f"Only VERIFIED reports can be assigned; current status is {report.status}."}
            )
        if not worker.is_active or worker.role != User.Role.WORKER:
            raise serializers.ValidationError({"worker_id": "Selected user must be an active WORKER."})

        report.status = Report.Status.ASSIGNED
        report.assigned_worker = worker
        report.assigned_at = timezone.now()
        report.save(update_fields=["status", "assigned_worker", "assigned_at", "updated_at"])

        worker_name = worker.get_full_name().strip() or worker.email
        cls._history(report, actor, note or f"Assigned to worker {worker_name}.")
        cls._notify(
            report,
            "Worker assigned",
            "A field worker has been assigned to your environmental report.",
        )
        create_notification(
            user=worker,
            title="New job assigned",
            message=f"A {report.category.name} report has been assigned to you.",
            notification_type=Notification.Type.REPORT_STATUS,
            report=report,
        )
        return report

    @classmethod
    @transaction.atomic
    def start(cls, report_id, worker, note=""):
        report = cls._locked(report_id)
        if report.status != Report.Status.ASSIGNED:
            raise serializers.ValidationError(
                {"status": f"Only ASSIGNED reports can be started; current status is {report.status}."}
            )
        if report.assigned_worker_id != worker.id:
            raise serializers.ValidationError({"detail": "This report is not assigned to you."})

        report.status = Report.Status.IN_PROGRESS
        report.started_at = timezone.now()
        report.save(update_fields=["status", "started_at", "updated_at"])

        cls._history(report, worker, note or "Assigned worker started work on the report.")
        cls._notify(
            report,
            "Work started",
            "Work has started on your environmental report.",
        )
        return report

    @classmethod
    @transaction.atomic
    def resolve(cls, report_id, worker, images, note=""):
        report = cls._locked(report_id)
        if report.status != Report.Status.IN_PROGRESS:
            raise serializers.ValidationError(
                {"status": f"Only IN_PROGRESS reports can be resolved; current status is {report.status}."}
            )
        if report.assigned_worker_id != worker.id:
            raise serializers.ValidationError({"detail": "This report is not assigned to you."})
        if not images:
            raise serializers.ValidationError({"images": "At least one AFTER image is required."})

        for image in images:
            ReportImage.objects.create(
                report=report,
                image=image,
                image_type=ReportImage.ImageType.AFTER,
                uploaded_by=worker,
            )

        report.status = Report.Status.RESOLVED
        report.resolved_at = timezone.now()
        report.save(update_fields=["status", "resolved_at", "updated_at"])

        cls._history(report, worker, note or "Report resolved with after-photo evidence.")
        cls._notify(
            report,
            "Report resolved",
            "Your environmental report has been marked resolved. Resolution photos are now available.",
        )
        return report
