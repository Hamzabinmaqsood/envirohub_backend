from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.reports.models import Category, Report, ReportConfirmation, ReportFollow


class AuthorityCommunityEngagementTests(TestCase):
    def setUp(self):
        self.authority = User.objects.create_user(
            email="authority-dashboard@example.com",
            password="TestPass123!",
            role=User.Role.AUTHORITY,
        )
        self.owner = User.objects.create_user(
            email="owner-dashboard@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.community_user = User.objects.create_user(
            email="community-dashboard@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        category = Category.objects.create(
            name="Dashboard Waste",
            slug="dashboard-waste",
        )
        self.report = Report.objects.create(
            citizen=self.owner,
            category=category,
            description="Community metrics test",
            location=Point(73.0479, 33.6844, srid=4326),
        )
        ReportConfirmation.objects.create(
            report=self.report,
            user=self.community_user,
        )
        ReportFollow.objects.create(
            report=self.report,
            user=self.community_user,
        )
        self.client.force_login(self.authority)

    def test_overview_exposes_global_community_metrics(self):
        response = self.client.get(reverse("authority-dashboard:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["community_confirmations"], 1)
        self.assertEqual(response.context["active_follows"], 1)
        recent = list(response.context["recent_reports"])
        self.assertEqual(recent[0].confirmation_count, 1)
        self.assertEqual(recent[0].follower_count, 1)

    def test_report_list_and_detail_expose_per_report_counts(self):
        response = self.client.get(reverse("authority-dashboard:reports"))
        self.assertEqual(response.status_code, 200)
        listed = response.context["page"].object_list[0]
        self.assertEqual(listed.confirmation_count, 1)
        self.assertEqual(listed.follower_count, 1)

        detail = self.client.get(
            reverse("authority-dashboard:report-detail", args=[self.report.id])
        )
        self.assertEqual(detail.status_code, 200)
        shown = detail.context["report"]
        self.assertEqual(shown.confirmation_count, 1)
        self.assertEqual(shown.follower_count, 1)
