from django.contrib.gis.geos import Point
from django.db import IntegrityError, transaction
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.reports.models import Category, Report, ReportConfirmation, ReportFollow


class CommunityApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="community-owner@example.com", password="TestPass123!", role=User.Role.CITIZEN
        )
        self.citizen = User.objects.create_user(
            email="community-observer@example.com", password="TestPass123!", role=User.Role.CITIZEN
        )
        self.second = User.objects.create_user(
            email="community-second@example.com", password="TestPass123!", role=User.Role.CITIZEN
        )
        self.worker = User.objects.create_user(
            email="community-worker@example.com", password="TestPass123!", role=User.Role.WORKER
        )
        self.category = Category.objects.create(name="Waste", slug="waste")
        self.report = Report.objects.create(
            citizen=self.owner, category=self.category, description="Garbage near road",
            location=Point(73.0479, 33.6844, srid=4326),
        )
        self.base = f"/api/v1/reports/{self.report.id}/"
        self.client.force_authenticate(user=self.citizen)

    def test_confirmation_is_idempotent_and_independent_of_follow(self):
        r = self.client.post(self.base + "confirm/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["confirmation_count"], r.data["follower_count"]), (1, 0))
        self.assertTrue(r.data["is_confirmed"])
        r = self.client.post(self.base + "confirm/")
        self.assertEqual(r.data["confirmation_count"], 1)
        r = self.client.post(self.base + "follow/")
        self.assertEqual((r.data["confirmation_count"], r.data["follower_count"]), (1, 1))
        self.assertTrue(r.data["is_following"])
        self.assertEqual(ReportConfirmation.objects.count(), 1)
        self.assertEqual(ReportFollow.objects.count(), 1)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.SUBMITTED)

    def test_withdraw_and_unfollow_are_idempotent(self):
        self.client.post(self.base + "confirm/")
        self.client.post(self.base + "follow/")
        self.assertEqual(self.client.delete(self.base + "confirm/").data["confirmation_count"], 0)
        self.assertEqual(self.client.delete(self.base + "confirm/").data["confirmation_count"], 0)
        self.assertEqual(self.client.delete(self.base + "follow/").data["follower_count"], 0)
        self.assertEqual(self.client.delete(self.base + "follow/").data["follower_count"], 0)

    def test_unique_database_constraints(self):
        ReportConfirmation.objects.create(report=self.report, user=self.citizen)
        ReportFollow.objects.create(report=self.report, user=self.citizen)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReportConfirmation.objects.create(report=self.report, user=self.citizen)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReportFollow.objects.create(report=self.report, user=self.citizen)

    def test_owner_cannot_confirm_or_follow_own_report(self):
        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.post(self.base + "confirm/").status_code, 400)
        self.assertEqual(self.client.post(self.base + "follow/").status_code, 400)
        self.assertEqual(ReportConfirmation.objects.count(), 0)
        self.assertEqual(ReportFollow.objects.count(), 0)

    def test_worker_cannot_access_community_endpoints(self):
        self.client.force_authenticate(user=self.worker)
        for url in ("confirm/", "follow/", "community/", "following/"):
            path = "/api/v1/reports/" if url == "following/" else self.base
            response = self.client.get(path + url) if url in ("community/", "following/") else self.client.post(path + url)
            self.assertEqual(response.status_code, 403)

    def test_private_report_detail_stays_private_while_community_view_is_safe(self):
        self.assertEqual(self.client.get(self.base).status_code, 404)
        response = self.client.get(self.base + "community/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("citizen", response.data)
        self.assertNotIn("timeline", response.data)
        self.assertNotIn("assigned_worker", response.data)
        self.assertEqual(response.data["confirmation_count"], 0)

    def test_owner_detail_preserves_original_timeline_and_assignment_fields(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200)
        self.assertIn("timeline", response.data)
        self.assertIn("assigned_worker", response.data)
        self.assertIn("images", response.data)
        self.assertEqual(response.data["confirmation_count"], 0)

    def test_resolved_and_rejected_reports_not_open_to_new_participation(self):
        self.report.status = Report.Status.RESOLVED
        self.report.save(update_fields=["status"])
        self.assertEqual(self.client.post(self.base + "confirm/").status_code, 400)
        self.assertEqual(self.client.post(self.base + "follow/").status_code, 400)
        self.report.status = Report.Status.REJECTED
        self.report.save(update_fields=["status"])
        self.assertEqual(self.client.get(self.base + "community/").status_code, 404)
        self.assertEqual(self.client.post(self.base + "confirm/").status_code, 404)

    def test_existing_engagement_can_be_withdrawn_after_resolution(self):
        self.client.post(self.base + "confirm/")
        self.client.post(self.base + "follow/")
        self.report.status = Report.Status.RESOLVED
        self.report.save(update_fields=["status"])
        self.assertEqual(self.client.delete(self.base + "confirm/").status_code, 200)
        self.assertEqual(self.client.delete(self.base + "follow/").status_code, 200)

    def test_following_feed_contains_only_current_users_follows(self):
        self.client.post(self.base + "follow/")
        self.client.force_authenticate(user=self.second)
        self.client.post(self.base + "follow/")
        response = self.client.get("/api/v1/reports/following/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.client.force_authenticate(user=self.citizen)
        response = self.client.get("/api/v1/reports/following/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(str(response.data["results"][0]["id"]), str(self.report.id))
        self.assertTrue(response.data["results"][0]["is_following"])
        self.assertEqual(response.data["results"][0]["follower_count"], 2)

    def test_nearby_counts_and_personal_flags_are_independent(self):
        self.client.post(self.base + "confirm/")
        self.client.post(self.base + "follow/")
        self.client.force_authenticate(user=self.second)
        response = self.client.get("/api/v1/reports/nearby/", {
            "latitude": 33.6844, "longitude": 73.0479, "radius_m": 200,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["confirmation_count"], 1)
        self.assertEqual(response.data[0]["follower_count"], 1)
        self.assertFalse(response.data[0]["is_confirmed"])
        self.assertFalse(response.data[0]["is_following"])
        self.client.force_authenticate(user=self.citizen)
        response = self.client.get("/api/v1/reports/nearby/", {
            "latitude": 33.6844, "longitude": 73.0479, "radius_m": 200,
        })
        self.assertTrue(response.data[0]["is_confirmed"])
        self.assertTrue(response.data[0]["is_following"])

    def test_unknown_report_returns_404(self):
        import uuid
        missing = f"/api/v1/reports/{uuid.uuid4()}/"
        self.assertEqual(self.client.get(missing + "community/").status_code, 404)
        self.assertEqual(self.client.post(missing + "confirm/").status_code, 404)
