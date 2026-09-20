import logging

from django.conf import settings
from django.db import transaction

from .models import DeviceInstallation, Notification

logger = logging.getLogger(__name__)


def create_notification(*, user, title, message, notification_type=Notification.Type.GENERAL, report=None):
    """Persist an in-app notification and send push only after the DB commit succeeds."""
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        report=report,
    )
    transaction.on_commit(lambda: send_push_notification(notification.pk))
    return notification


def _firebase_app():
    if not getattr(settings, "FIREBASE_PUSH_ENABLED", False):
        return None

    try:
        import firebase_admin
    except ImportError:
        logger.warning("Firebase push is enabled but firebase-admin is not installed.")
        return None

    try:
        return firebase_admin.get_app()
    except ValueError:
        options = {}
        project_id = getattr(settings, "FIREBASE_PROJECT_ID", "").strip()
        if project_id:
            options["projectId"] = project_id
        try:
            return firebase_admin.initialize_app(options=options or None)
        except Exception:
            logger.exception("Could not initialize Firebase Admin SDK; push delivery skipped.")
            return None


def send_push_notification(notification_id):
    app = _firebase_app()
    if app is None:
        return 0

    notification = Notification.objects.select_related("report").filter(pk=notification_id).first()
    if notification is None:
        return 0

    # Existing FID-only rows remain saved but are NOT push destinations until the
    # Flutter client re-registers with a valid FCM token. No failing fid= retry.
    installations = DeviceInstallation.objects.filter(
        user=notification.user,
        is_active=True,
    ).exclude(fcm_registration_token="").only("pk", "fcm_registration_token")

    from firebase_admin import messaging

    data = {
        "notification_id": str(notification.id),
        "notification_type": notification.notification_type,
    }
    if notification.report_id:
        data["report_id"] = str(notification.report_id)

    sent = 0
    for installation in installations:
        try:
            messaging.send(
                messaging.Message(
                    notification=messaging.Notification(
                        title=notification.title,
                        body=notification.message,
                    ),
                    data=data,
                    # Compatibility path for FlutterFire getToken().
                    # Switch to fid= only after client-side FID registration is supported.
                    token=installation.fcm_registration_token,
                ),
                app=app,
            )
            sent += 1
        except messaging.UnregisteredError:
            # FCM explicitly rejected this destination. Keep the FID record so a
            # subsequent login/token refresh can reactivate it with a fresh token.
            DeviceInstallation.objects.filter(pk=installation.pk).update(
                is_active=False,
                fcm_registration_token="",
            )
            logger.warning("FCM destination unregistered; device %s deactivated", installation.pk)
        except Exception:
            # Push delivery must never break the report/status transaction.
            # Never log registration tokens or service account credentials.
            logger.exception(
                "FCM delivery failed for notification %s device %s",
                notification.id,
                installation.pk,
            )
    return sent
