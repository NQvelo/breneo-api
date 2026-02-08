# Remove UserProfile records for users who have an Academy (profiles belong only in Academy table)

from django.db import migrations


def remove_academy_user_profiles(apps, schema_editor):
    """Delete UserProfile records for users who have an Academy."""
    UserProfile = apps.get_model("app", "UserProfile")
    Academy = apps.get_model("app", "Academy")

    academy_user_ids = Academy.objects.values_list("user_id", flat=True).distinct()
    UserProfile.objects.filter(user_id__in=academy_user_ids).delete()


def reverse_remove(apps, schema_editor):
    """Cannot restore deleted profiles - data is lost."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0064_academy_use_user_for_name_email"),
    ]

    operations = [
        migrations.RunPython(remove_academy_user_profiles, reverse_remove),
    ]
