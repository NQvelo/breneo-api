# Generated manually for SubscriptionPlan.audience

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0088_seed_atoms_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptionplan",
            name="audience",
            field=models.CharField(
                choices=[
                    ("user", "User"),
                    ("academy", "Academy"),
                    ("company", "Company"),
                ],
                db_index=True,
                default="user",
                help_text="Who this plan is for: User, Academy, or Company.",
                max_length=20,
            ),
        ),
    ]
