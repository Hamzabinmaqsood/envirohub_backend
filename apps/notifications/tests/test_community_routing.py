from django.contrib.gis.geos import Point
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.reports.models import Category, Report, ReportFollow


class NotificationCommunityRoutingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="owner-routing@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.follower = User.objects.create_user(
            email="follower-routing@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        category = Category.objects.create(
            name="Routing Waste",
            slug="routing-waste",
        )
        self.report = Report.objects.create(
            citizen=self.owner,
            category=category,
            description="Routing test",
            location=Point(73.0479, 33.6844, srid=4326),
        )
        ReportFollow.objects.create(report=self.report, user=self.follower)

    def test_notification_marks_followed_report_for_community_detail(self):
        Notification.objects.create(
            user=self.follower,
            title="Report verified",
            message="A report you follow has been verified.",
            notification_type=Notification.Type.REPORT_STATUS,
            report=self.report,
        )
        self.client.force_authenticate(self.follower)

        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, 200)
        row = response.data["results"][0] if isinstance(response.data, dict) else response.data[0]
        self.assertEqual(str(row["report_id"]), str(self.report.id))
        self.assertTrue(row["is_community_report"])

    def test_owner_notification_keeps_private_owner_detail_route(self):
        Notification.objects.create(
            user=self.owner,
            title="Report verified",
            message="Your report has been verified.",
            notification_type=Notification.Type.REPORT_STATUS,
            report=self.report,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, 200)
        row = response.data["results"][0] if isinstance(response.data, dict) else response.data[0]
        self.assertFalse(row["is_community_report"])
