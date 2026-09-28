import warnings

from django.contrib.gis.geos import Point
from django.core.paginator import UnorderedObjectListWarning
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.reports.models import Category, Report


class AuthorityMapHardeningTests(TestCase):
    def setUp(self):
        self.authority = User.objects.create_user(
            email="authority-map@example.com",
            password="TestPass123!",
            role=User.Role.AUTHORITY,
        )
        self.citizen = User.objects.create_user(
            email="citizen-map@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.category = Category.objects.create(
            name="Map Test",
            slug="map-test",
        )
        self.report = Report.objects.create(
            citizen=self.citizen,
            category=self.category,
            description="Map policy regression test",
            location=Point(73.0479, 33.6844, srid=4326),
        )
        self.client.force_login(self.authority)

    def test_live_map_uses_canonical_openstreetmap_tile_url(self):
        response = self.client.get(reverse("authority-dashboard:map"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        )
        self.assertNotContains(
            response,
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        )
        self.assertEqual(
            response.headers.get("Referrer-Policy"),
            "strict-origin-when-cross-origin",
        )

    def test_report_detail_uses_canonical_openstreetmap_tile_url(self):
        response = self.client.get(
            reverse("authority-dashboard:report-detail", args=[self.report.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        )
        self.assertNotContains(
            response,
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        )
        self.assertEqual(
            response.headers.get("Referrer-Policy"),
            "strict-origin-when-cross-origin",
        )

    def test_report_list_pagination_has_deterministic_ordering(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", UnorderedObjectListWarning)
            response = self.client.get(reverse("authority-dashboard:reports"))

        self.assertEqual(response.status_code, 200)
        unordered = [
            warning
            for warning in caught
            if issubclass(warning.category, UnorderedObjectListWarning)
        ]
        self.assertEqual(unordered, [])
