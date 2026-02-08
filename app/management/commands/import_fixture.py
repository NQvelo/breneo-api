"""
Load old data from a Django fixture JSON file.

Usage:
  python manage.py import_fixture path/to/backup.json
  python manage.py import_fixture app/fixtures/initial_questions.json

The file should be from: python manage.py dumpdata app -o backup.json
(on the project that has the data).
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
import os


class Command(BaseCommand):
    help = "Load data from a fixture JSON file (e.g. from dumpdata on another database)."

    def add_arguments(self, parser):
        parser.add_argument(
            "fixture_path",
            type=str,
            help="Path to the fixture JSON file (e.g. backup.json or app/fixtures/initial.json)",
        )

    def handle(self, *args, **options):
        path = options["fixture_path"]
        if not os.path.isfile(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        self.stdout.write(f"Loading fixture: {path}")
        try:
            call_command("loaddata", path, verbosity=2)
            self.stdout.write(self.style.SUCCESS("Fixture loaded successfully."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Load failed: {e}"))
