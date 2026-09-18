from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.reports.models import Category, Report


class NearbyReportsApiTests(APITestCase):
    def setUp(self):
        self.citizen = User.objects.create_user(
            email="nearby-citizen@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.other_citizen = User.objects.create_user(
            email="other-citizen@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.garbage = Category.objects.create(name="Garbage", slug="garbage")
        self.sewage = Category.objects.create(name="Sewage", slug="sewage")
        self.client.force_authenticate(self.citizen)

    def _report(self, *, lon, lat, category=None, status=Report.Status.SUBMITTED):
        return Report.objects.create(
            citizen=self.other_citizen,
            category=category or self.garbage,
            description="Nearby environmental issue",
            location=Point(lon, lat, srid=4326),
            status=status,
        )

    def test_nearby_returns_open_reports_in_distance_order(self):
        close = self._report(lon=73.04795, lat=33.68445)
        self._report(lon=73.04900, lat=33.68500)
        self._report(lon=73.15000, lat=33.78000)
        self._report(
            lon=73.04796,
            lat=33.68446,
            status=Report.Status.RESOLVED,
        )

        response = self.client.get(
            "/api/v1/reports/nearby/",
            {
                "latitude": 33.6844,
                "longitude": 73.0479,
                "radius_m": 500,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["id"], str(close.id))
        self.assertGreaterEqual(response.data[0]["distance_m"], 0)
        self.assertLessEqual(response.data[0]["distance_m"], response.data[1]["distance_m"])

    def test_nearby_can_filter_by_category(self):
        garbage = self._report(lon=73.04795, lat=33.68445, category=self.garbage)
        self._report(lon=73.04796, lat=33.68446, category=self.sewage)

        response = self.client.get(
            "/api/v1/reports/nearby/",
            {
                "latitude": 33.6844,
                "longitude": 73.0479,
                "radius_m": 300,
                "category": "garbage",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(garbage.id))
        self.assertEqual(response.data[0]["category"]["slug"], "garbage")
