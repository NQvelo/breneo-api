"""Seed Atom rows for career-path professions."""

from django.core.management.base import BaseCommand
from django.db import transaction

from app.atom_schemas import validate_content_cards, validate_quiz_data
from app.data.atoms_seed_data import ATOMS_SEED
from app.models import Atom, Profession


class Command(BaseCommand):
    help = "Seed Atoms for Frontend Developer, UI/UX Designer, and Product Owner professions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing atoms for seeded profession titles before inserting.",
        )

    def handle(self, *args, **options):
        titles = [entry["title"] for entry in ATOMS_SEED]

        with transaction.atomic():
            if options["clear"]:
                deleted_atoms, _ = Atom.objects.filter(profession__title__in=titles).delete()
                self.stdout.write(
                    self.style.WARNING(f"Cleared {deleted_atoms} atom-related objects.")
                )

            created_professions = 0
            created_atoms = 0

            for entry in ATOMS_SEED:
                profession, created = Profession.objects.get_or_create(
                    title=entry["title"],
                    defaults={"description": entry["description"]},
                )
                if created:
                    created_professions += 1
                    self.stdout.write(self.style.SUCCESS(f"Created profession: {profession.title}"))
                elif entry["description"] and profession.description != entry["description"]:
                    profession.description = entry["description"]
                    profession.save(update_fields=["description", "updated_at"])
                    self.stdout.write(f"Updated profession description: {profession.title}")
                else:
                    self.stdout.write(f"Profession: {profession.title}")

                for atom_data in entry["atoms"]:
                    content_cards = validate_content_cards(atom_data["content_cards"])
                    quiz_data = validate_quiz_data(atom_data["quiz_data"])

                    atom, atom_created = Atom.objects.update_or_create(
                        profession=profession,
                        sequence_order=atom_data["sequence_order"],
                        defaults={
                            "title": atom_data["title"],
                            "content_cards": content_cards,
                            "quiz_data": quiz_data,
                        },
                    )
                    if atom_created:
                        created_atoms += 1
                    self.stdout.write(f"  · Atom #{atom.sequence_order}: {atom.title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created_professions} new professions, {created_atoms} new atoms."
            )
        )
