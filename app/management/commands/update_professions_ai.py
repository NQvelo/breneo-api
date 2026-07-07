import time
from django.core.management.base import BaseCommand
from app.models import Profession
from app.utils import fetch_profession_description_from_groq


class Command(BaseCommand):
    help = "Update existing professions with description data from Groq AI."

    def handle(self, *args, **options):
        professions = Profession.objects.all()
        total = professions.count()
        self.stdout.write(f"Found {total} professions to update.")

        for i, profession in enumerate(professions, 1):
            self.stdout.write(f"[{i}/{total}] Updating {profession.title}...")

            desc = fetch_profession_description_from_groq(profession.title)
            if desc:
                profession.description = desc
                profession.save(update_fields=["description", "updated_at"])
                self.stdout.write("   - Rich description updated.")

            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {total} professions."))
