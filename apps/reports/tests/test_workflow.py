from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import serializers

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.reports.models import Category, Report, ReportFollow, ReportImage, ReportStatusHistory
from apps.reports.services import ReportWorkflow


_ONE_PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


class ReportWorkflowTests(TestCase):
    def setUp(self):
        self.citizen = User.objects.create_user(
            email="citizen@example.com",
            password="TestPass123!",
            first_name="Citizen",
            role=User.Role.CITIZEN,
        )
        self.authority = User.objects.create_user(
            email="authority@example.com",
            password="TestPass123!",
            first_name="Authority",
            role=User.Role.AUTHORITY,
        )
        self.worker = User.objects.create_user(
            email="worker@example.com",
            password="TestPass123!",
            first_name="Worker",
            role=User.Role.WORKER,
        )
        self.other_worker = User.objects.create_user(
            email="other-worker@example.com",
            password="TestPass123!",
            role=User.Role.WORKER,
        )
        self.follower = User.objects.create_user(
            email="follower@example.com",
            password="TestPass123!",
            first_name="Follower",
            role=User.Role.CITIZEN,
        )
        self.former_follower = User.objects.create_user(
            email="former-follower@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.category = Category.objects.create(
            name="Garbage",
            slug="garbage",
            description="Solid waste",
        )
        self.report = Report.objects.create(
            citizen=self.citizen,
            category=self.category,
            description="Overflowing waste bin",
            location=Point(73.0479, 33.6844, srid=4326),
        )

    def test_complete_authority_to_worker_workflow(self):
        ReportWorkflow.verify(self.report.id, self.authority, "Evidence verified")
        ReportWorkflow.assign(self.report.id, self.authority, self.worker, "Assigned")
        ReportWorkflow.start(self.report.id, self.worker, "Cleanup started")

        after_photo = SimpleUploadedFile(
            "after.gif",
            _ONE_PIXEL_GIF,
            content_type="image/gif",
        )
        ReportWorkflow.resolve(
            self.report.id,
            self.worker,
            [after_photo],
            "Area cleaned",
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.RESOLVED)
        self.assertEqual(self.report.verified_by, self.authority)
        self.assertEqual(self.report.assigned_worker, self.worker)
        self.assertIsNotNone(self.report.verified_at)
        self.assertIsNotNone(self.report.assigned_at)
        self.assertIsNotNone(self.report.started_at)
        self.assertIsNotNone(self.report.resolved_at)

        self.assertEqual(
            list(
                ReportStatusHistory.objects.filter(report=self.report).values_list(
                    "status", flat=True
                )
            ),
            [
                Report.Status.VERIFIED,
                Report.Status.ASSIGNED,
                Report.Status.IN_PROGRESS,
                Report.Status.RESOLVED,
            ],
        )
        self.assertEqual(
            ReportImage.objects.filter(
                report=self.report,
                image_type=ReportImage.ImageType.AFTER,
            ).count(),
            1,
        )
        self.assertEqual(
            list(
                Notification.objects.filter(user=self.citizen)
                .order_by("created_at")
                .values_list("title", flat=True)
            ),
            [
                "Report verified",
                "Worker assigned",
                "Work started",
                "Report resolved",
            ],
        )
        self.assertEqual(
            list(
                Notification.objects.filter(user=self.worker)
                .order_by("created_at")
                .values_list("title", flat=True)
            ),
            ["New job assigned"],
        )

    def test_unassigned_worker_cannot_start_report(self):
        self.report.status = Report.Status.ASSIGNED
        self.report.assigned_worker = self.worker
        self.report.save(update_fields=["status", "assigned_worker", "updated_at"])

        with self.assertRaises(serializers.ValidationError):
            ReportWorkflow.start(self.report.id, self.other_worker)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.ASSIGNED)

    def test_report_cannot_be_assigned_before_verification(self):
        with self.assertRaises(serializers.ValidationError):
            ReportWorkflow.assign(
                self.report.id,
                self.authority,
                self.worker,
            )

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.SUBMITTED)

    def test_current_followers_receive_each_status_notification(self):
        ReportFollow.objects.create(report=self.report, user=self.follower)

        ReportWorkflow.verify(self.report.id, self.authority)
        ReportWorkflow.assign(self.report.id, self.authority, self.worker)
        ReportWorkflow.start(self.report.id, self.worker)

        after_photo = SimpleUploadedFile(
            "after-follower.gif",
            _ONE_PIXEL_GIF,
            content_type="image/gif",
        )
        ReportWorkflow.resolve(self.report.id, self.worker, [after_photo])

        self.assertEqual(
            list(
                Notification.objects.filter(user=self.follower)
                .order_by("created_at")
                .values_list("title", flat=True)
            ),
            [
                "Report verified",
                "Worker assigned",
                "Work started",
                "Report resolved",
            ],
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.follower,
                message__icontains="report you follow",
            ).exists()
        )

    def test_unfollow_stops_future_status_notifications(self):
        ReportFollow.objects.create(report=self.report, user=self.former_follower)

        ReportWorkflow.verify(self.report.id, self.authority)
        ReportFollow.objects.filter(
            report=self.report,
            user=self.former_follower,
        ).delete()
        ReportWorkflow.assign(self.report.id, self.authority, self.worker)
        ReportWorkflow.start(self.report.id, self.worker)

        after_photo = SimpleUploadedFile(
            "after-unfollow.gif",
            _ONE_PIXEL_GIF,
            content_type="image/gif",
        )
        ReportWorkflow.resolve(self.report.id, self.worker, [after_photo])

        self.assertEqual(
            list(
                Notification.objects.filter(user=self.former_follower)
                .order_by("created_at")
                .values_list("title", flat=True)
            ),
            ["Report verified"],
        )

    def test_reporter_never_gets_duplicate_notification_from_legacy_follow(self):
        # The API prevents this state, but the workflow still defensively de-duplicates it.
        ReportFollow.objects.create(report=self.report, user=self.citizen)

        ReportWorkflow.verify(self.report.id, self.authority)

        self.assertEqual(
            Notification.objects.filter(
                user=self.citizen,
                report=self.report,
                title="Report verified",
            ).count(),
            1,
        )

