# Generated manually — unify LearningModule into Profession

import django.db.models.deletion
from django.db import migrations, models


def migrate_atoms_to_professions(apps, schema_editor):
    LearningModule = apps.get_model("app", "LearningModule")
    Profession = apps.get_model("app", "Profession")
    Atom = apps.get_model("app", "Atom")

    for atom in Atom.objects.select_related("module").iterator():
        module = atom.module
        profession, created = Profession.objects.get_or_create(
            title=module.title,
            defaults={"description": module.description or ""},
        )
        if not created and module.description and not profession.description:
            profession.description = module.description
            profession.save(update_fields=["description"])
        atom.profession = profession
        atom.save(update_fields=["profession"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0085_atom_json_examples"),
    ]

    operations = [
        migrations.AddField(
            model_name="atom",
            name="profession",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="atoms",
                to="app.profession",
            ),
        ),
        migrations.RunPython(migrate_atoms_to_professions, noop_reverse),
        migrations.RemoveConstraint(
            model_name="atom",
            name="unique_atom_sequence_per_module",
        ),
        migrations.RemoveIndex(
            model_name="atom",
            name="app_atom_module__f1c3e3_idx",
        ),
        migrations.RemoveField(
            model_name="atom",
            name="module",
        ),
        migrations.AlterField(
            model_name="atom",
            name="profession",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="atoms",
                to="app.profession",
            ),
        ),
        migrations.AddConstraint(
            model_name="atom",
            constraint=models.UniqueConstraint(
                fields=("profession", "sequence_order"),
                name="unique_atom_sequence_per_profession",
            ),
        ),
        migrations.AddIndex(
            model_name="atom",
            index=models.Index(
                fields=["profession", "sequence_order"],
                name="app_atom_profess_8a1c2d_idx",
            ),
        ),
        migrations.DeleteModel(
            name="LearningModule",
        ),
    ]
