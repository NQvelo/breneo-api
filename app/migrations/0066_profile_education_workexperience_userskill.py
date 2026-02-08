# Profile fields, Education, WorkExperience, UserSkill (created_at + unique constraint)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def remove_duplicate_user_skills(apps, schema_editor):
    """Keep one UserSkill per (user, skill); delete duplicates so unique constraint can be added."""
    UserSkill = apps.get_model("app", "UserSkill")
    seen = set()
    to_delete = []
    for us in UserSkill.objects.order_by("id"):
        key = (us.user_id, us.skill_id)
        if key in seen:
            to_delete.append(us.id)
        else:
            seen.add(key)
    if to_delete:
        UserSkill.objects.filter(id__in=to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0065_remove_academy_profiles_from_userprofile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # UserProfile: add country_region, city
        migrations.AddField(
            model_name="userprofile",
            name="country_region",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        # UserSkill: add created_at
        migrations.AddField(
            model_name="userskill",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        # Remove duplicate (user, skill) rows before adding unique constraint
        migrations.RunPython(remove_duplicate_user_skills, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="userskill",
            constraint=models.UniqueConstraint(
                fields=("user", "skill"),
                name="unique_user_skill",
            ),
        ),
        # Education
        migrations.CreateModel(
            name="Education",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("school_name", models.CharField(max_length=255)),
                ("major", models.CharField(blank=True, default="", max_length=255)),
                ("degree_type", models.CharField(blank=True, default="", max_length=100)),
                ("gpa", models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("is_current", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="educations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        # WorkExperience
        migrations.CreateModel(
            name="WorkExperience",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_title", models.CharField(max_length=255)),
                ("company", models.CharField(max_length=255)),
                ("job_type", models.CharField(blank=True, default="", max_length=100)),
                ("location", models.CharField(blank=True, default="", max_length=255)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("is_current", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_experiences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
