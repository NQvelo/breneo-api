# Seed Atoms learning content on deploy (idempotent — safe to re-run).

from django.db import migrations


def seed_atoms_forward(apps, schema_editor):
    from app.atom_seed import seed_atoms

    seed_atoms()


def seed_atoms_backward(apps, schema_editor):
    Atom = apps.get_model("app", "Atom")
    titles = [
        "Frontend Developer",
        "UI/UX Designer",
        "Product Owner",
    ]
    Atom.objects.filter(profession__title__in=titles).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0087_remove_profession_salary_info"),
    ]

    operations = [
        migrations.RunPython(seed_atoms_forward, seed_atoms_backward),
    ]
