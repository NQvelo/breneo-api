"""
Remove duplicate SkillTestResult rows.
Keeps the most recent result per user, deletes the rest.
Run periodically (e.g. daily cron) or manually:
  python manage.py cleanup_skill_test_duplicates
"""
from django.core.management.base import BaseCommand
from app.models import SkillTestResult


class Command(BaseCommand):
    help = "Remove duplicate SkillTestResult rows (keep most recent per user)"

    def handle(self, *args, **options):
        removed = 0
        user_ids = SkillTestResult.objects.values_list("user_id", flat=True).distinct()
        for user_id in user_ids:
            results = list(
                SkillTestResult.objects.filter(user_id=user_id).order_by("-created_at")
            )
            if len(results) > 1:
                to_keep = results[0]
                for r in results[1:]:
                    r.delete()
                    removed += 1
        self.stdout.write(
            self.style.SUCCESS(f"Removed {removed} duplicate SkillTestResult row(s).")
        )
