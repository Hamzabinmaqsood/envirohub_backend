from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0002_report_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportConfirmation",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="confirmations", to="reports.report")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="report_confirmations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("report", "user"), name="reports_confirm_once")]},
        ),
        migrations.CreateModel(
            name="ReportFollow",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followers", to="reports.report")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followed_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("report", "user"), name="reports_follow_once")],
                "indexes": [models.Index(fields=("user", "report"), name="reports_follow_user_idx")],
            },
        ),
    ]
