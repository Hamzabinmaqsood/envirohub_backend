from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.notifications.models import DeviceInstallation, Notification
from apps.notifications.services import create_notification, send_push_notification


class DeviceInstallationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="citizen-push@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.other = User.objects.create_user(
            email="other-push@example.com",
            password="TestPass123!",
            role=User.Role.CITIZEN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_register_and_unregister_installation(self):
        response = self.client.post(
            "/api/v1/notification-devices/",
            {"firebase_installation_id": "fid-test-123", "platform": "ANDROID"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        installation = DeviceInstallation.objects.get(firebase_installation_id="fid-test-123")
        self.assertEqual(installation.user, self.user)
        self.assertTrue(installation.is_active)

        response = self.client.post(
            "/api/v1/notification-devices/unregister/",
            {"firebase_installation_id": "fid-test-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        installation.refresh_from_db()
        self.assertFalse(installation.is_active)

    def test_same_installation_is_reassigned_to_current_user(self):
        DeviceInstallation.objects.create(
            user=self.other,
            firebase_installation_id="fid-shared-123",
            platform=DeviceInstallation.Platform.ANDROID,
        )
        response = self.client.post(
            "/api/v1/notification-devices/",
            {"firebase_installation_id": "fid-shared-123", "platform": "ANDROID"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        installation = DeviceInstallation.objects.get(firebase_installation_id="fid-shared-123")
        self.assertEqual(installation.user, self.user)
        self.assertTrue(installation.is_active)

    def test_in_app_notification_still_works_when_push_disabled(self):
        created = create_notification(
            user=self.user,
            title="Test notification",
            message="Stored even without Firebase credentials.",
            notification_type=Notification.Type.GENERAL,
        )
        self.assertTrue(Notification.objects.filter(pk=created.pk, user=self.user).exists())

    def test_register_token_write_only_and_refresh(self):
        response = self.client.post(
            "/api/v1/notification-devices/",
            {
                "firebase_installation_id": "fid-token-test",
                "fcm_registration_token": "token-version-one",
                "platform": "ANDROID",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("fcm_registration_token", response.data)
        device = DeviceInstallation.objects.get(firebase_installation_id="fid-token-test")
        self.assertEqual(device.fcm_registration_token, "token-version-one")
        response = self.client.post(
            "/api/v1/notification-devices/",
            {
                "firebase_installation_id": "fid-token-test",
                "fcm_registration_token": "token-version-two",
                "platform": "ANDROID",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        device.refresh_from_db()
        self.assertEqual(device.fcm_registration_token, "token-version-two")
        response = self.client.get("/api/v1/notification-devices/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("fcm_registration_token", str(response.data))

    def test_push_targets_flutterfire_token_not_fid(self):
        DeviceInstallation.objects.create(
            user=self.user,
            firebase_installation_id="fid-test-send",
            fcm_registration_token="fcm-token-test-send",
            platform=DeviceInstallation.Platform.ANDROID,
        )
        notification = Notification.objects.create(
            user=self.user,
            title="Worker job",
            message="New assigned job",
        )
        with patch("apps.notifications.services._firebase_app", return_value=object()):
            with patch("firebase_admin.messaging.send", return_value="message-id") as send:
                self.assertEqual(send_push_notification(notification.pk), 1)
        sent_message = send.call_args.args[0]
        self.assertEqual(sent_message.token, "fcm-token-test-send")
        self.assertIsNone(sent_message.fid)

    def test_fid_only_legacy_installation_not_targeted(self):
        DeviceInstallation.objects.create(
            user=self.user,
            firebase_installation_id="fid-legacy",
            platform=DeviceInstallation.Platform.ANDROID,
        )
        notification = Notification.objects.create(
            user=self.user,
            title="Test",
            message="In-app only until next registration",
        )
        with patch("apps.notifications.services._firebase_app", return_value=object()):
            with patch("firebase_admin.messaging.send") as send:
                self.assertEqual(send_push_notification(notification.pk), 0)
                send.assert_not_called()
