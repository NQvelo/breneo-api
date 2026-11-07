"""Section parser used when no LLM key is configured, and as a fallback."""

from __future__ import annotations

import re

from app.ats.schemas.resume import (
    BilingualText,
    EducationItem,
    ResumeData,
    SkillItem,
    WorkExperienceItem,
)
from app.ats.textutil import detect_language, georgian_count, latin_count

_SECTION_HEADERS = {
    "summary": {
        "summary",
        "profile",
        "about",
        "about me",
        "objective",
        "შეჯამება",
        "პროფილი",
        "ჩემ შესახებ",
        "მიზანი",
    },
    "experience": {
        "experience",
        "work experience",
        "employment",
        "work history",
        "professional experience",
        "გამოცდილება",
        "სამუშაო გამოცდილება",
        "სამუშაო ისტორია",
    },
    "education": {
        "education",
        "academic background",
        "განათლება",
    },
    "skills": {
        "skills",
        "technical skills",
        "core skills",
        "უნარები",
        "უნარ-ჩვევები",
        "ტექნიკური უნარები",
    },
    "languages": {
        "languages",
        "ენები",
    },
    "certifications": {
        "certifications",
        "certificates",
        "licenses",
        "სერტიფიკატები",
        "სერტიფიკატი",
    },
}

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,4}\)[\s-]?)?\d[\d\s\-()]{6,}\d")
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_PRESENT_RE = re.compile(
    r"\b(present|current|now|ongoing|დღემდე|მიმდინარე|დღეს)\b",
    re.IGNORECASE,
)


def extract_with_heuristics(text: str, filename: str = "") -> ResumeData:
    sections = _split_sections(text or "")
    email_match = _EMAIL_RE.search(text or "")
    full_name, headline = _name_and_headline(sections.get("preamble", ""))
    experience = _parse_experience(sections.get("experience", ""))
    education = _parse_education(sections.get("education", ""))
    skills = _parse_skills(sections.get("skills", ""))
    if not skills:
        skills = _skills_from_commas(text or "")
    summary_source = sections.get("summary") or _preamble_summary(sections.get("preamble", ""), full_name)
    resume = ResumeData(
        full_name=_as_bilingual(full_name),
        headline=_as_bilingual(headline),
        email=email_match.group(0) if email_match else None,
        phone=_find_phone(text or ""),
        summary=_as_bilingual(summary_source),
        skills=skills,
        languages=_parse_skills(sections.get("languages", "")),
        work_experience=experience,
        education=education,
        certifications=_parse_certifications(sections.get("certifications", "")),
        language=detect_language(text or ""),
        extraction_method="heuristic",
        source_filename=filename,
    )
    return resume


def _as_bilingual(text: str) -> BilingualText:
    cleaned = (text or "").strip()
    if not cleaned:
        return BilingualText()
    language = detect_language(cleaned)
    if language == "ka":
        return BilingualText(ka=cleaned)
    if language == "en":
        return BilingualText(en=cleaned)
    english_parts: list[str] = []
    georgian_parts: list[str] = []
    for token in re.findall(r"\S+", cleaned):
        script = detect_language(token)
        if script == "ka" or (script == "mixed" and georgian_count(token) >= latin_count(token)):
            georgian_parts.append(token)
        else:
            english_parts.append(token)
    return BilingualText(en=" ".join(english_parts), ka=" ".join(georgian_parts))


def _normalize_header(line: str) -> str:
    normalized = line.strip().lower()
    normalized = re.sub(r"^[#*\-\d\.\)\s]+", "", normalized)
    return normalized.strip(" :|-—–")


def _match_header(line: str) -> str | None:
    normalized = _normalize_header(line)
    if not normalized or len(normalized) > 48:
        return None
    for key, names in _SECTION_HEADERS.items():
        if normalized in names:
            return key
    return None


def _split_sections(text: str) -> dict[str, str]:
    buckets: dict[str, list[str]] = {"preamble": []}
    current = "preamble"
    for line in text.splitlines():
        header = _match_header(line)
        if header:
            current = header
            buckets.setdefault(current, [])
            continue
        buckets.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in buckets.items()}


def _name_and_headline(preamble: str) -> tuple[str, str]:
    lines = [line.strip() for line in preamble.splitlines() if line.strip()]
    if not lines:
        return "", ""
    name = ""
    headline = ""
    for line in lines:
        if _EMAIL_RE.search(line) or _find_phone(line):
            continue
        if not name and _looks_like_name(line):
            name = line
            continue
        if name and not headline and len(line) <= 120:
            headline = line
            break
    return name, headline


def _looks_like_name(line: str) -> bool:
    if len(line) > 80 or any(char.isdigit() for char in line):
        return False
    words = re.findall(r"[A-Za-z\u10A0-\u10FF]+", line)
    return 2 <= len(words) <= 5


def _preamble_summary(preamble: str, name: str) -> str:
    lines = []
    for line in preamble.splitlines():
        stripped = line.strip()
        if not stripped or stripped == name or _EMAIL_RE.search(stripped):
            continue
        lines.append(stripped)
    return " ".join(lines[:4])


def _find_phone(text: str) -> str | None:
    for match in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if 8 <= len(digits) <= 15:
            return match.group(0).strip()
    return None


def _parse_skills(text: str) -> list[SkillItem]:
    if not text.strip():
        return []
    chunks = re.split(r"[,;•|\n]|(?:\s+-\s+)|(?:\s+·\s+)", text)
    skills: list[SkillItem] = []
    seen: set[str] = set()
    for chunk in chunks:
        name = chunk.strip(" -•\t:|")
        if not name or len(name) < 2 or len(name) > 80:
            continue
        if _match_header(name):
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        bilingual = _as_bilingual(name)
        skills.append(SkillItem(name_en=bilingual.en, name_ka=bilingual.ka))
    return skills


def _skills_from_commas(text: str) -> list[SkillItem]:
    best: list[SkillItem] = []
    for line in text.splitlines():
        if line.count(",") < 2:
            continue
        parsed = _parse_skills(line)
        if len(parsed) > len(best):
            best = parsed
    return best


def _parse_certifications(text: str) -> list[BilingualText]:
    items = []
    for line in text.splitlines():
        stripped = line.strip(" -•\t")
        if stripped:
            items.append(_as_bilingual(stripped))
    return items


def _blocks(text: str) -> list[str]:
    if not text.strip():
        return []
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _extract_date_span(text: str) -> tuple[str | None, str | None, bool] | None:
    years = _YEAR_RE.findall(text)
    current = bool(_PRESENT_RE.search(text))
    if not years and not current:
        return None
    start = years[0] if years else None
    if current:
        return start, None, True
    end = years[-1] if len(years) >= 2 else None
    return start, end, False


def _split_role_header(line: str) -> tuple[str, str]:
    cleaned = _YEAR_RE.sub(" ", line)
    cleaned = _PRESENT_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[\(\)\[\]|,–—\-/]+", "|", cleaned)
    parts = [part.strip(" |-") for part in cleaned.split("|") if part.strip(" |-")]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _parse_experience(text: str) -> list[WorkExperienceItem]:
    roles: list[WorkExperienceItem] = []
    blocks = _blocks(text) or ([text] if text.strip() else [])
    for block in blocks:
        lines = [line.strip("•-* \t") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        span = _extract_date_span(block)
        title, company = _split_role_header(lines[0])
        description = " ".join(lines[1:])
        if not title and not company and not description:
            continue
        roles.append(
            WorkExperienceItem(
                title=_as_bilingual(title),
                company=_as_bilingual(company),
                description=_as_bilingual(description),
                start_date=span[0] if span else None,
                end_date=span[1] if span else None,
                is_current=span[2] if span else False,
            )
        )
    return roles


def _parse_education(text: str) -> list[EducationItem]:
    items: list[EducationItem] = []
    blocks = _blocks(text) or ([text] if text.strip() else [])
    for block in blocks:
        lines = [line.strip("•-* \t") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        span = _extract_date_span(block)
        school, degree = _split_role_header(lines[0])
        field = " ".join(lines[1:])
        items.append(
            EducationItem(
                school=_as_bilingual(school),
                degree=_as_bilingual(degree),
                field_of_study=_as_bilingual(field),
                start_date=span[0] if span else None,
                end_date=span[1] if span else None,
                is_current=span[2] if span else False,
            )
        )
    return items
