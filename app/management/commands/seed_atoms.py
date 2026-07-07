"""Seed Atom rows for career-path professions."""

from django.core.management.base import BaseCommand

from app.atom_seed import seed_atoms as run_seed_atoms


class Command(BaseCommand):
    help = "Seed Atoms for Frontend Developer, UI/UX Designer, and Product Owner professions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing atoms for seeded profession titles before inserting.",
        )

    def handle(self, *args, **options):
        result = run_seed_atoms(clear=options["clear"], stdout=self.stdout)
        self.stdout.write(
            self.style.SUCCESS(
                "Done. "
                f"{result['created_professions']} new professions, "
                f"{result['created_atoms']} new atoms, "
                f"{result['updated_atoms']} updated atoms."
            )
        )
