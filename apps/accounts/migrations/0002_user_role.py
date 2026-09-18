from django.db import migrations, models


def mark_superusers_as_authorities(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=True).update(role="AUTHORITY")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("CITIZEN", "Citizen"),
                    ("WORKER", "Worker"),
                    ("AUTHORITY", "Authority"),
                ],
                db_index=True,
                default="CITIZEN",
                max_length=20,
            ),
        ),
        migrations.RunPython(mark_superusers_as_authorities, migrations.RunPython.noop),
    ]
