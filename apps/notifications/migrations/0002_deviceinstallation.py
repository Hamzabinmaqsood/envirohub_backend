import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceInstallation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("firebase_installation_id", models.CharField(db_index=True, max_length=255, unique=True)),
                (
                    "platform",
                    models.CharField(
                        choices=[
                            ("ANDROID", "Android"),
                            ("IOS", "iOS"),
                            ("WEB", "Web"),
                            ("OTHER", "Other"),
                        ],
                        default="OTHER",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="device_installations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.AddIndex(
            model_name="deviceinstallation",
            index=models.Index(fields=["user", "is_active"], name="notif_user_active_idx"),
        ),
    ]
