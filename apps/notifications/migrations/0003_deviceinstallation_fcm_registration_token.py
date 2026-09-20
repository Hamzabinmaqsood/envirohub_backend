from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_deviceinstallation"),
    ]

    operations = [
        migrations.AddField(
            model_name="deviceinstallation",
            name="fcm_registration_token",
            field=models.CharField(blank=True, default="", max_length=2048),
        ),
    ]
