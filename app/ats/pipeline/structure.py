"""Turn an ordered resume into sections, jobs, and schools."""

from __future__ import annotations

import re

from app.ats.extractor.experience import parse_experience_blocks
from app.ats.schemas.resume import BilingualText, EducationItem, ResumeData, SkillItem
from app.ats.textutil import detect_language

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,4}\)[\s-]?)?\d[\d\s\-()]{6,}\d")
_LINK_RE = re.compile(
    r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+|(?:linkedin|github|behance|dribbble)\.com/[^\s<>\"']+)",
    re.IGNORECASE,
)
_DEGREE_RE = re.compile(
    r"\b(bachelor|master|phd|doctorate|bsc|msc|ba|ma|mba|degree|diploma|associate|ბაკალავრ\w*|მაგისტრ\w*|დოქტორ\w*)\b",
    re.IGNORECASE,
)
_SCHOOL_RE = re.compile(
    r"(university|college|school|institute|academy|უნივერსიტეტ\w*|სკოლა|კოლეჯ\w*|ინსტიტუტ\w*)",
    re.IGNORECASE,
)
_RANGE_RE = re.compile(
    r"(?P<start>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}[./]\d{2,4}|\d{4}[./]\d{1,2}|(?:19|20)\d{2})"
    r"\s*[-–—]+\s*"
    r"(?P<end>present|current|now|ongoing|დღემდე|მიმდინარე|დღეს|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}[./]\d{2,4}|\d{4}[./]\d{1,2}|(?:19|20)\d{2})",
    re.IGNORECASE,
)
_SECTIONS = {
    "summary": {"summary", "profile", "about", "about me", "objective", "professional profile", "შეჯამება", "პროფილი", "ჩემ შესახებ"},
    "experience": {"experience", "work experience", "professional experience", "employment", "career history", "employment history", "career", "გამოცდილება", "სამუშაო გამოცდილება", "სამუშაო ისტორია"},
    "education": {"education", "academic background", "academic experience", "qualifications", "studies", "განათლება"},
    "skills": {"skills", "technical skills", "core competencies", "competencies", "expertise", "უნარები", "უნარ-ჩვევები", "ტექნიკური უნარები"},
    "languages": {"languages", "ენები"},
    "certifications": {"certifications", "certificates", "licenses", "სერტიფიკატები"},
}


def build_resume(text: str, filename: str = "") -> ResumeData:
    """Extract fields from layout-ordered text. Each job comes from one block."""
    sections = _sections(text)
    email = _first(_EMAIL_RE, text)
    phone = _phone(text)
    links = []
    for match in _LINK_RE.findall(text or ""):
        link = match.rstrip(".,);")
        if link not in links:
            links.append(link)
    summary = _same(sections.get("summary", ""))
    skills = _skills(sections.get("skills", ""))
    jobs = parse_experience_blocks(text)
    schools = _education(sections.get("education", ""))
    name, headline = _identity(sections.get("preamble", ""))
    resume = ResumeData(
        full_name=_same(name),
        headline=_same(headline),
        email=email,
        phone=phone,
        summary=summary,
        skills=skills,
        languages=_skills(sections.get("languages", "")),
        work_experience=jobs,
        education=schools,
        certifications=[_same(line) for line in _lines(sections.get("certifications", ""))],
        links=links,
        language=detect_language(text or ""),
        extraction_method="heuristic",
        source_filename=filename,
    )
    return _repair(resume)


def _sections(text: str) -> dict[str, str]:
    buckets: dict[str, list[str]] = {"preamble": []}
    current = "preamble"
    for line in (text or "").splitlines():
        key = _heading(line)
        if key:
            current = key
            buckets.setdefault(current, [])
            continue
        buckets.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in buckets.items()}


def _heading(line: str) -> str:
    normalized = re.sub(r"^[#*\-\d\.\)\s]+", "", line.strip().lower()).strip(" :|-—–")
    if not normalized or len(normalized) > 48:
        return ""
    for key, names in _SECTIONS.items():
        if normalized in names:
            return key
    return ""


def _education(text: str) -> list[EducationItem]:
    items: list[EducationItem] = []
    for block in [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()] or ([text] if text.strip() else []):
        lines = [line.strip() for line in block.splitlines() if line.strip() and not _heading(line)]
        if not lines:
            continue
        degree = ""
        field = ""
        school = ""
        start = end = None
        current = False
        for line in lines:
            match = _RANGE_RE.search(line)
            if match and not start:
                start = match.group("start").strip()
                end = match.group("end").strip()
                current = end.casefold() in {"present", "current", "now", "ongoing", "დღემდე", "მიმდინარე", "დღეს"}
                continue
            if _SCHOOL_RE.search(line) and not school:
                school = line
                continue
            if _DEGREE_RE.search(line) and not degree:
                degree, field = _split_degree(line)
                continue
        if not school:
            for line in lines:
                if line not in {degree, field, school} and not _RANGE_RE.search(line):
                    school = line
                    break
        if degree or school:
            items.append(
                EducationItem(
                    school=_same(school),
                    degree=_same(degree),
                    field_of_study=_same(field),
                    start_date=start,
                    end_date=end,
                    is_current=current,
                )
            )
    return items


def _split_degree(line: str) -> tuple[str, str]:
    match = re.search(r"\s+\b(in|of)\b\s+", line, re.IGNORECASE)
    if not match:
        return line.strip(), ""
    return line[: match.start()].strip(), line[match.end() :].strip()


def _skills(text: str) -> list[SkillItem]:
    items: list[SkillItem] = []
    seen: set[str] = set()
    for chunk in re.split(r"[,;•|\n]|(?:\s+-\s+)", text or ""):
        name = chunk.strip(" -•\t:|")
        if not name or len(name) < 2 or len(name) > 80 or _heading(name):
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(SkillItem(name_en=name, name_ka=name))
    return items


def _identity(preamble: str) -> tuple[str, str]:
    lines = [line.strip() for line in preamble.splitlines() if line.strip()]
    name = ""
    headline = ""
    for line in lines:
        if _EMAIL_RE.search(line) or _PHONE_RE.search(line) or _LINK_RE.search(line):
            continue
        if not name and 2 <= len(re.findall(r"[A-Za-z\u10A0-\u10FF]+", line)) <= 5 and len(line) <= 80 and not any(ch.isdigit() for ch in line):
            name = line
            continue
        if name and not headline and len(line) <= 120:
            headline = line
            break
    return name, headline


def _repair(resume: ResumeData) -> ResumeData:
    unique = []
    seen: set[tuple[str, str, str]] = set()
    for job in resume.work_experience:
        title = (job.title.en or job.title.ka).strip()
        company = (job.company.en or job.company.ka).strip()
        if not title and not company:
            continue
        key = (title.casefold(), company.casefold(), (job.start_date or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    resume.work_experience = unique
    return resume


def _lines(text: str) -> list[str]:
    return [line.strip(" -•\t") for line in (text or "").splitlines() if line.strip()]


def _same(text: str) -> BilingualText:
    cleaned = (text or "").strip()
    return BilingualText(en=cleaned, ka=cleaned)


def _first(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text or "")
    return match.group(0) if match else None


def _phone(text: str) -> str | None:
    for match in _PHONE_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", match.group(0))
        if 8 <= len(digits) <= 15:
            return match.group(0).strip()
    return None
