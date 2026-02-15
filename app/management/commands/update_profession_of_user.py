"""
Update ProfessionOfUser table: assign users to matched professions
based on SkillScore (only skills with score > 0).

Run: python manage.py update_profession_of_user
"""
from django.core.management.base import BaseCommand
from app.profession_match import update_all_profession_assignments


class Command(BaseCommand):
    help = "Match users to professions from SkillScore (score > 0) and update ProfessionOfUser"

    def handle(self, *args, **options):
        update_all_profession_assignments()
        self.stdout.write(self.style.SUCCESS("✅ ProfessionOfUser table updated."))
