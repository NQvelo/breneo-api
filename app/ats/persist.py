"""Store a parsed CV and copy it onto the profile fields the frontend already renders."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from django.db import transaction

from app.ats.schemas.resume import BilingualText, ResumeData

logger = logging.getLogger(__name__)

_MAX_ROWS = 10
_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y")
_MONTH_NUMBERS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def save_parsed_resume(user, resume: ResumeData):
    """Persist the formatted CV and write its details onto the user's profile page."""
    from app.models import UserResume

    _keep_registered_name(user, resume)
    payload = resume.model_dump(mode="json")
    with transaction.atomic():
        record, _created = UserResume.objects.update_or_create(
            user=user,
            defaults={
                "data": payload,
                "source_filename": (resume.source_filename or "")[:255],
            },
        )
    try:
        with transaction.atomic():
            _apply_to_profile(user, resume)
    except Exception:
        logger.exception("Parsed CV was saved, but copying it onto the profile failed for user %s", user.pk)
    return record


def _apply_to_profile(user, resume: ResumeData) -> None:
    from app.models import Academy, Education, Employer, Skill, UserProfile, UserSkill, WorkExperience

    if not Academy.objects.filter(user_id=user.pk).exists() and not Employer.objects.filter(user_id=user.pk).exists():
        _write_identity(user, resume)

    if resume.education:
        Education.objects.filter(user=user).delete()
        for item in resume.education[:_MAX_ROWS]:
            school = _primary(item.school) or _primary(item.degree) or _primary(item.field_of_study)
            if not school:
                continue
            start, end, current = _dates(item.start_date, item.end_date, item.is_current)
            Education.objects.create(
                user=user,
                school_name=school[:255],
                major=_primary(item.field_of_study)[:255],
                degree_type=_primary(item.degree)[:100],
                start_date=start,
                end_date=end,
                is_current=current,
            )

    if resume.work_experience:
        WorkExperience.objects.filter(user=user).delete()
        for item in resume.work_experience[:_MAX_ROWS]:
            title = _primary(item.title) or _primary(item.company) or _primary(item.description)
            if not title:
                continue
            start, end, current = _dates(item.start_date, item.end_date, item.is_current)
            WorkExperience.objects.create(
                user=user,
                job_title=title[:255],
                company=(_primary(item.company) or "")[:255],
                location=_primary(item.location)[:255],
                start_date=start,
                end_date=end,
                is_current=current,
            )

    for skill in resume.skills[:30]:
        name = (skill.name_en or skill.name_ka or "").strip()
        if not name:
            continue
        normalized = " ".join(name.split())[:100]
        row = Skill.objects.filter(name__iexact=normalized).first()
        if row is None:
            row = Skill.objects.create(name=normalized)
        UserSkill.objects.get_or_create(user=user, skill=row, defaults={"points": 1})


def _keep_registered_name(user, resume: ResumeData) -> None:
    """The name shown to the app is the one entered at registration, not the CV."""
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    registered = " ".join(part for part in (first, last) if part)
    if not registered:
        return
    resume.full_name = BilingualText(en=registered, ka=registered)


def _write_identity(user, resume: ResumeData) -> None:
    """Copy contact details onto the profile. The registered name is left unchanged."""
    from app.models import UserProfile

    profile, _created = UserProfile.objects.get_or_create(user=user)
    changed = []
    if resume.phone:
        profile.phone_number = resume.phone[:20]
        changed.append("phone_number")
    about = _text(resume.summary) or _text(resume.headline)
    if about:
        profile.about_me = about
        changed.append("about_me")
    city = _primary(resume.location)
    if city:
        profile.city = city[:100]
        changed.append("city")
    if changed:
        profile.save(update_fields=changed)


def _primary(value: BilingualText | None) -> str:
    """One script for single-line profile fields. English wins when both exist."""
    if value is None:
        return ""
    return (value.en or "").strip() or (value.ka or "").strip()


def _text(value: BilingualText | None) -> str:
    if value is None:
        return ""
    english = (value.en or "").strip()
    georgian = (value.ka or "").strip()
    if english and georgian and english != georgian:
        return f"{english}\n{georgian}"
    return english or georgian


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    named = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{4})", text)
    if named and named.group(1).lower()[:3] in _MONTH_NUMBERS:
        return date(int(named.group(2)), _MONTH_NUMBERS[named.group(1).lower()[:3]], 1)
    slash = re.fullmatch(r"(\d{1,2})[./](\d{4})", text)
    if slash and 1 <= int(slash.group(1)) <= 12:
        return date(int(slash.group(2)), int(slash.group(1)), 1)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        if fmt == "%Y":
            return date(parsed.year, 1, 1)
        if fmt == "%Y-%m":
            return date(parsed.year, parsed.month, 1)
        return parsed
    return None


def _dates(start_raw: str | None, end_raw: str | None, is_current: bool) -> tuple[date | None, date | None, bool]:
    start = _parse_date(start_raw)
    end = None if is_current else _parse_date(end_raw)
    if start and end and start > end:
        end = None
    return start, end, bool(is_current)
