"""
Fetch and populate Profession data: description, salary, market popularity.
Uses Groq AI (GROQ_API_KEY). Auto-links relevant_courses by matching profession
skills with course skills_taught.

Optional APIs for real data (add to .env when available):
- BLS API: https://www.bls.gov/developers/ - Occupational Employment & Wages
- CareerOneStop: https://careeronestop.org/Developers/WebAPI/ - Salary by occupation

Run: python manage.py fetch_profession_data
      python manage.py fetch_profession_data --skip-groq   # use defaults, no API
      python manage.py fetch_profession_data --dry-run     # preview only
"""
import json
import os
import re
from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Profession, Skill, Course, Job


# Real professions only (job titles). Excludes soft/behavioral roles like Team Player, Problem Solver, etc.
PROFESSION_SKILLS = {
    "Frontend Developer": ["React", "Vue", "Angular", "JavaScript", "TypeScript", "UI/UX"],
    "Backend Developer": ["Python", "Django", "Flask", "Node.js", "Express.js"],
    "iOS Developer": ["iOS", "Swift"],
    "Android Developer": ["Android", "Kotlin"],
    "React Native Developer": ["React Native", "JavaScript"],
    "UI/UX Designer": ["UI/UX", "Figma", "Design"],
    "Graphic Designer": ["Graphic Designer", "Design", "Photoshop"],
    "Product Designer": ["Product Designer", "UI/UX", "Design"],
    "3D Modeler": ["3D Modeler", "Blender", "3D"],
    "Content Creator": ["Content Creator", "Video Editor", "Copywriter"],
    "Data Analyst": ["SQL", "MongoDB", "Data Analyst", "Python"],
    "DevOps Engineer": ["DevOps", "AWS", "Docker", "Kubernetes"],
    "Project Manager": ["Project Management", "Leadership", "Task Management"],
}

# Titles to remove from Profession table (not real job titles)
NON_PROFESSION_TITLES = {
    "Team Player",
    "Problem Solver",
    "Efficient Planner",
    "Organized Worker",
    "Leader / Manager",
    "Curious Learner",
    "Proactive Learner",
    "Unknown Job",
}


def fetch_from_groq(prompt: str, fallback: str = "") -> str:
    """Fetch data from Groq AI. Returns fallback on error."""
    try:
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            return fallback
        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or fallback).strip()
    except Exception:
        return fallback


SALARY_REGIONS = ["US", "Germany", "Georgia", "Turkey", "UK", "Other"]


def parse_salary_entry(text: str, currency: str = "USD", symbol: str = "$") -> dict:
    """Parse salary string like '$70,000 - $120,000' into {min, max, currency, display}."""
    text = text or ""
    nums = [int(m.replace(",", "")) for m in re.findall(r"\d{1,3}(?:,\d{3})*", text)]
    if len(nums) >= 2:
        lo, hi = min(nums), max(nums)
        return {"min": lo, "max": hi, "currency": currency, "display": f"{symbol}{lo:,} - {symbol}{hi:,}"}
    if len(nums) == 1:
        return {"min": nums[0], "max": nums[0], "currency": currency, "display": f"{symbol}{nums[0]:,}"}
    return {"min": 0, "max": 0, "currency": currency, "display": "N/A"}


def build_salary_info_object(prompt_response: str, title: str) -> dict:
    """
    Parse Groq response into salary_info object: {US: {...}, Germany: {...}, ...}
    Falls back to defaults if parsing fails.
    """
    symbols = {"US": "$", "Germany": "€", "Georgia": "₾", "Turkey": "₺", "UK": "£", "Other": "$"}
    currencies = {"US": "USD", "Germany": "EUR", "Georgia": "GEL", "Turkey": "TRY", "UK": "GBP", "Other": "USD"}
    defaults = {
        "US": {"min": 70000, "max": 120000, "currency": "USD", "display": "$70,000 - $120,000"},
        "Germany": {"min": 55000, "max": 95000, "currency": "EUR", "display": "€55,000 - €95,000"},
        "Georgia": {"min": 18000, "max": 45000, "currency": "GEL", "display": "₾18,000 - ₾45,000"},
        "Turkey": {"min": 300000, "max": 700000, "currency": "TRY", "display": "₺300,000 - ₺700,000"},
        "UK": {"min": 45000, "max": 90000, "currency": "GBP", "display": "£45,000 - £90,000"},
        "Other": {"min": 40000, "max": 80000, "currency": "USD", "display": "$40,000 - $80,000"},
    }
    try:
        start = prompt_response.find("{")
        end = prompt_response.rfind("}") + 1
        if start >= 0 and end > start:
            obj = json.loads(prompt_response[start:end])
            out = {}
            for region in SALARY_REGIONS:
                val = obj.get(region, obj.get(region.lower(), defaults[region]))
                if isinstance(val, dict) and "min" in val and "max" in val:
                    sym = symbols.get(region, "$")
                    cur = val.get("currency", currencies.get(region, "USD"))
                    out[region] = {
                        "min": int(val["min"]),
                        "max": int(val["max"]),
                        "currency": cur,
                        "display": val.get("display", f"{sym}{val['min']:,} - {sym}{val['max']:,}"),
                    }
                else:
                    out[region] = defaults[region]
            return out
    except Exception:
        pass
    return defaults


class Command(BaseCommand):
    help = "Fetch description, salary, market popularity for professions; auto-link courses"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Don't save, just print")
        parser.add_argument("--skip-groq", action="store_true", help="Skip Groq fetches, use defaults only")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_groq = options["skip_groq"]

        # Remove non-profession entries (soft/behavioral roles, Unknown Job, etc.)
        to_remove = Profession.objects.filter(title__in=NON_PROFESSION_TITLES)
        removed_count = to_remove.count()
        if not dry_run and removed_count:
            to_remove.delete()
            self.stdout.write(self.style.WARNING(f"Removed {removed_count} non-profession(s): {list(NON_PROFESSION_TITLES)}"))
        elif dry_run and removed_count:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would remove {removed_count} non-profession(s)"))

        # Only create/update real professions from our mapping (not every Job title)
        titles = set(PROFESSION_SKILLS.keys())

        for title in sorted(titles):
            self.stdout.write(f"Processing: {title}")
            skill_names = PROFESSION_SKILLS.get(title, [])

            # Get or create skills
            skills = []
            for name in skill_names:
                s, _ = Skill.objects.get_or_create(name=name)
                skills.append(s)

            # Get Job for skills if we have it
            job = Job.objects.filter(title__iexact=title).first()
            if job:
                for s in job.required_skills.all():
                    if s not in skills:
                        skills.append(s)

            # Fetch description
            if skip_groq:
                description = f"{title} is a career role that combines relevant technical and soft skills."
            else:
                desc = fetch_from_groq(
                    f"Write a 2-3 sentence professional description of the career '{title}'. "
                    "Focus on what the role does and who it's for. Be concise.",
                    fallback=f"{title} is a career path.",
                )
                description = desc[:2000] if desc else ""

            # Fetch salary (one object: US, Germany, Georgia, Turkey, UK, Other)
            if skip_groq:
                salary_info = {
                    "US": {"min": 70000, "max": 120000, "currency": "USD", "display": "$70,000 - $120,000"},
                    "Germany": {"min": 55000, "max": 95000, "currency": "EUR", "display": "€55,000 - €95,000"},
                    "Georgia": {"min": 18000, "max": 45000, "currency": "GEL", "display": "₾18,000 - ₾45,000"},
                    "Turkey": {"min": 300000, "max": 700000, "currency": "TRY", "display": "₺300,000 - ₺700,000"},
                    "UK": {"min": 45000, "max": 90000, "currency": "GBP", "display": "£45,000 - £90,000"},
                    "Other": {"min": 40000, "max": 80000, "currency": "USD", "display": "$40,000 - $80,000"},
                }
            else:
                sal_prompt = (
                    f"For a {title} with mid-level experience, provide yearly salary ranges for these regions. "
                    "Return a single JSON object with keys: US, Germany, Georgia, Turkey, UK, Other. "
                    "Each value: {{\"min\": number, \"max\": number, \"currency\": \"XXX\", \"display\": \"formatted string\"}}. "
                    "Use: USD/$ for US, EUR/€ for Germany, GEL/₾ for Georgia, TRY/₺ for Turkey, GBP/£ for UK. "
                    "Other = global average in USD. Example: {{\"US\": {{\"min\": 70000, \"max\": 120000, \"currency\": \"USD\", \"display\": \"$70,000 - $120,000\"}}, ...}}"
                )
                sal_text = fetch_from_groq(sal_prompt, fallback="{}")
                salary_info = build_salary_info_object(sal_text, title)

            # Fetch market popularity (5-year trend for charts)
            if skip_groq:
                import random
                base = random.randint(60, 85)
                market_popularity = [
                    {"year": str(y), "value": base + (y - 2020) * 2 + random.randint(-2, 2)}
                    for y in range(2020, 2025)
                ]
            else:
                pop_text = fetch_from_groq(
                    f"For the occupation '{title}', provide market popularity index (0-100) for each year 2020-2024. "
                    "Return a JSON array: [{{\"year\":\"2020\",\"value\":75}}, ...]",
                    fallback="[]",
                )
                try:
                    # Try to extract JSON from response
                    start = pop_text.find("[")
                    end = pop_text.rfind("]") + 1
                    if start >= 0 and end > start:
                        market_popularity = json.loads(pop_text[start:end])
                    else:
                        market_popularity = []
                except Exception:
                    market_popularity = [
                        {"year": str(y), "value": 70 + (y - 2020) * 3}
                        for y in range(2020, 2025)
                    ]

            if not market_popularity or len(market_popularity) < 5:
                market_popularity = [
                    {"year": str(y), "value": 70 + (y - 2020) * 3}
                    for y in range(2020, 2025)
                ]

            # Relevant courses: courses that teach any of the profession's skills
            skill_names_set = {s.name for s in skills}
            relevant_courses = list(
                Course.objects.filter(skills_taught__name__in=skill_names_set).distinct()
            )

            if dry_run:
                self.stdout.write(f"  Would create/update: {title}")
                self.stdout.write(f"  Skills: {[s.name for s in skills]}")
                self.stdout.write(f"  Courses: {[c.title for c in relevant_courses[:5]]}...")
                continue

            with transaction.atomic():
                prof, created = Profession.objects.update_or_create(
                    title=title,
                    defaults={
                        "description": description,
                        "salary_info": salary_info,
                        "market_popularity": market_popularity,
                    },
                )
                prof.skills.set(skills)
                prof.relevant_courses.set(relevant_courses)

            self.stdout.write(self.style.SUCCESS(f"  {'Created' if created else 'Updated'}: {title}"))

        self.stdout.write(self.style.SUCCESS("✅ Profession data fetch complete."))
