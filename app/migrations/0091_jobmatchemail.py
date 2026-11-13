from django.conf import settings
from django.core.management import call_command
from django.db import migrations, models


def create_snapshot_cache_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0090_userresume"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="JobMatchEmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sent_on", models.DateField()),
                ("delivered", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="job_match_emails",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("user", "sent_on"), name="unique_job_match_email_per_day"),
                ],
            },
        ),
        migrations.RunPython(create_snapshot_cache_table, migrations.RunPython.noop),
    ]
