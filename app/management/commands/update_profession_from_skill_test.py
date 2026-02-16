"""
Populate ProfessionOfUser from SkillTestResult.skills_json.

Reads each user's latest SkillTestResult; skills_json format:
  {"soft": {"Teamwork": "0.0%", "Leadership": "0.0%", ...}, "tech": {"Python": "0.0%", "Node.js": "0.0%"}}
Only skills with percentage > 0 are used to match professions.

Run: python manage.py update_profession_from_skill_test
"""
from django.core.management.base import BaseCommand
from app.profession_match import update_all_profession_assignments_from_skill_test


class Command(BaseCommand):
    help = (
        "Update ProfessionOfUser from SkillTestResult.skills_json (soft + tech, percentage > 0). "
        "Uses each user's most recent test result."
    )

    def handle(self, *args, **options):
        update_all_profession_assignments_from_skill_test()
        self.stdout.write(self.style.SUCCESS("✅ ProfessionOfUser updated from SkillTestResult."))
