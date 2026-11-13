"""The one place that turns a user's stored profile into the snapshot the aggregator scores."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.core.cache import caches

TBILISI = ZoneInfo("Asia/Tbilisi")
SNAPSHOT_CACHE_ALIAS = "job_match_snapshots"
SNAPSHOT_TTL_SECONDS = 5 * 60

SENIORITY_UNKNOWN = "unknown"

# Order matters: the first rule that hits wins, so "Senior Lead" is senior.
_TITLE_RULES = (
    (re.compile(r"\bintern\b", re.IGNORECASE), "intern"),
    (re.compile(r"\b(junior|entry)\b", re.IGNORECASE), "junior"),
    (re.compile(r"\b(mid|middle|intermediate)\b", re.IGNORECASE), "mid"),
    (re.compile(r"\bsenior\b", re.IGNORECASE), "senior"),
    (re.compile(r"\b(lead|principal|staff)\b", re.IGNORECASE), "lead"),
)


def tbilisi_today() -> date:
    return datetime.now(TBILISI).date()


def snapshot_cache():
    return caches[SNAPSHOT_CACHE_ALIAS]


def snapshot_cache_key(user_id) -> str:
    return f"job-match-snapshot:{user_id}"


def invalidate_user_snapshot(user_id) -> None:
    snapshot_cache().delete(snapshot_cache_key(user_id))


def build_user_snapshot(user_id) -> dict:
    """Snapshot for one user, from whatever is stored now. Cached per user for 5 minutes."""
    cache = snapshot_cache()
    key = snapshot_cache_key(user_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    profile = {
        "skills": _skills(user_id),
        "industryYears": _industry_years(user_id),
        "languages": _languages(user_id),
    }
    profile.update(_seniority_and_years(user_id))

    snapshot = {"userId": str(user_id), "profileVersion": profile_version(profile), **profile}
    cache.set(key, snapshot, SNAPSHOT_TTL_SECONDS)
    return snapshot


def profile_version(profile: dict) -> str:
    fields = {
        "industryYears": dict(sorted(profile["industryYears"].items())),
        "languages": sorted(profile["languages"]),
        "seniority": profile["seniority"],
        "skills": sorted(profile["skills"]),
        "yearsExperienceTotal": profile["yearsExperienceTotal"],
    }
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _collapse(text: str) -> str:
    return " ".join(text.split())


def normalize_skill(value) -> str:
    if not isinstance(value, str):
        return ""
    return _collapse(value).lower()


def skill_test_skill_names(skills_json) -> list[str]:
    if not isinstance(skills_json, dict):
        return []
    names: list[str] = []
    for section in ("tech", "soft"):
        value = skills_json.get(section)
        if isinstance(value, dict):
            names.extend(k for k in value.keys() if isinstance(k, str))
        elif isinstance(value, list):
            names.extend(item for item in value if isinstance(item, str))
    return names


def _skills(user_id) -> list[str]:
    from app.models import SkillTestResult, UserSkill

    raw = list(UserSkill.objects.filter(user_id=user_id).values_list("skill__name", flat=True))
    latest = (
        SkillTestResult.objects.filter(user_id=user_id)
        .order_by("-created_at", "-id")
        .values_list("skills_json", flat=True)
        .first()
    )
    raw.extend(skill_test_skill_names(latest))
    return sorted({name for name in (normalize_skill(item) for item in raw) if name})


def years_experience_total(roles, today: date) -> float | None:
    """roles: iterables of (start_date, end_date, is_current). None when no role has usable dates."""
    total_days = 0
    counted = False
    for start, end, is_current in roles:
        if start is None:
            continue
        stop = today if is_current else end
        if stop is None or stop < start:
            continue
        total_days += (stop - start).days
        counted = True
    if not counted:
        return None
    return round(total_days / 365.25, 2)


def seniority_from_title(title: str) -> str | None:
    for pattern, level in _TITLE_RULES:
        if pattern.search(title or ""):
            return level
    return None


def seniority_from_years(years: float | None) -> str:
    if years is None:
        return SENIORITY_UNKNOWN
    if years < 3:
        return "junior"
    if years < 6:
        return "mid"
    return "senior"


def pick_title_role(roles):
    """roles: dicts with job_title, start_date, end_date, is_current, id."""
    if not roles:
        return None

    def key(*fields):
        # None sorts before every date; id breaks exact ties the same way every time.
        return lambda r: tuple((r[f] is not None, r[f] or date.min) for f in fields) + (r["id"],)

    current = [r for r in roles if r["is_current"]]
    if current:
        return max(current, key=key("start_date"))
    return max(roles, key=key("end_date", "start_date"))


def _seniority_and_years(user_id) -> dict:
    from app.models import WorkExperience

    roles = list(
        WorkExperience.objects.filter(user_id=user_id).values(
            "id", "job_title", "start_date", "end_date", "is_current"
        )
    )
    if not roles:
        return {"seniority": SENIORITY_UNKNOWN, "yearsExperienceTotal": None}

    years = years_experience_total(
        ((r["start_date"], r["end_date"], r["is_current"]) for r in roles), tbilisi_today()
    )
    chosen = pick_title_role(roles)
    level = seniority_from_title(chosen["job_title"]) or seniority_from_years(years)
    return {"seniority": level, "yearsExperienceTotal": years}


def _to_years(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_industry_years(raw) -> dict[str, float]:
    if isinstance(raw, dict):
        pairs = raw.items()
    elif isinstance(raw, list):
        pairs = ((item.get("tag"), item.get("years")) for item in raw if isinstance(item, dict))
    else:
        return {}

    totals: dict[str, float] = {}
    for tag, years in pairs:
        if not isinstance(tag, str):
            continue
        name = _collapse(tag).lower()
        number = _to_years(years)
        if not name or number is None:
            continue
        totals[name] = totals.get(name, 0.0) + number
    return {tag: round(years, 2) for tag, years in sorted(totals.items()) if years > 0}


def _industry_years(user_id) -> dict[str, float]:
    from app.models import UserIndustryProfile

    raw = (
        UserIndustryProfile.objects.filter(user_id=user_id)
        .values_list("industry_years_json", flat=True)
        .first()
    )
    return normalize_industry_years(raw)


def resume_languages(data) -> list[str]:
    if not isinstance(data, dict) or not isinstance(data.get("languages"), list):
        return []
    found = set()
    for item in data["languages"]:
        if isinstance(item, dict):
            text = item.get("name_en") or item.get("name_ka") or ""
        else:
            text = item
        if isinstance(text, str):
            text = _collapse(text)
            if text:
                found.add(text)
    return sorted(found)


def _languages(user_id) -> list[str]:
    from app.models import UserResume

    data = UserResume.objects.filter(user_id=user_id).values_list("data", flat=True).first()
    return resume_languages(data)
