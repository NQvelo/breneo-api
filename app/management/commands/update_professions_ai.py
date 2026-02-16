import time
from django.core.management.base import BaseCommand
from app.models import Profession
from app.utils import fetch_salary_from_groq, fetch_profession_description_from_groq

class Command(BaseCommand):
    help = "Update existing professions with salary and description data from Groq AI."

    def handle(self, *args, **options):
        professions = Profession.objects.all()
        total = professions.count()
        self.stdout.write(f"Found {total} professions to update.")

        locations = ["US", "Germany", "Georgia", "Turkey", "UK"]

        for i, profession in enumerate(professions, 1):
            self.stdout.write(f"[{i}/{total}] Updating {profession.title}...")
            
            # 1. Update description (Always update to ensure "rich" content)
            desc = fetch_profession_description_from_groq(profession.title)
            if desc:
                profession.description = desc
                self.stdout.write(f"   - Rich description updated.")

            # 2. Update salary info
            updated_salary_info = profession.salary_info or {}
            for loc in locations:
                # We skip if it already exists to save API tokens, 
                # or we can overwrite if requested. 
                # For now, let's overwrite to ensure data is fresh if running this command.
                range_str = fetch_salary_from_groq(profession.title, loc)
                if range_str and range_str != "N/A":
                    # Simple parsing of "$70,000 - $120,000"
                    # Min/Max extraction could be added here, but for now we store the display string.
                    updated_salary_info[loc] = {
                        "min": 0, # Could be parsed from range_str if needed
                        "max": 0, # Could be parsed from range_str if needed
                        "currency": "USD" if loc != "Georgia" else "GEL",
                        "display": range_str
                    }
                    self.stdout.write(f"   - Salary for {loc}: {range_str}")
            
            profession.salary_info = updated_salary_info
            profession.save()
            
            # Throttle a bit to avoid hitting rate limits too fast
            time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {total} professions."))
