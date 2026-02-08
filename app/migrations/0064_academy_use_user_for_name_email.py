# Generated manually for Academy refactor: name/email from User

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_users_for_academies(apps, schema_editor):
    """For each Academy without a user, create a User from name/email and link it."""
    Academy = apps.get_model("app", "Academy")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for academy in Academy.objects.filter(user__isnull=True):
        user = User.objects.create(
            username=academy.email,
            email=academy.email,
            first_name=academy.name,
            last_name="",
            password=academy.password,
            is_active=True,
        )
        academy.user = user
        academy.save()


def reverse_create_users(apps, schema_editor):
    """Reverse: we cannot restore name/email from User easily - this is a one-way migration."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("app", "0063_job_charfield_pk"),
    ]

    operations = [
        # First: ensure every Academy has a user (for those with null user)
        migrations.RunPython(create_users_for_academies, reverse_create_users),
        # Remove name and email, make user required
        migrations.RemoveField(
            model_name="academy",
            name="name",
        ),
        migrations.RemoveField(
            model_name="academy",
            name="email",
        ),
        migrations.AlterField(
            model_name="academy",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="academy",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
