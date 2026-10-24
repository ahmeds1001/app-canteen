"""The company works Saturdays: the canteen opens Monday to Saturday (decided 2026-10-24)."""
from django.db import migrations, models

OLD, NEW = "0,1,2,3,4", "0,1,2,3,4,5"


def open_saturdays(apps, schema_editor):
    # Only rows still on the old default; a value the admin already chose is kept.
    apps.get_model("core", "CanteenSettings").objects.filter(service_weekdays=OLD).update(service_weekdays=NEW)


def close_saturdays(apps, schema_editor):
    apps.get_model("core", "CanteenSettings").objects.filter(service_weekdays=NEW).update(service_weekdays=OLD)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="canteensettings",
            name="service_weekdays",
            field=models.CharField(
                default=NEW,
                help_text="Days the canteen opens (0=Monday … 6=Sunday). Decided: Monday to Saturday.",
                max_length=20,
            ),
        ),
        migrations.RunPython(open_saturdays, close_saturdays),
    ]
