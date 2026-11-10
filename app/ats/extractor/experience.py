"""Pair each job title with the company and dates that belong to the same block."""

from __future__ import annotations

import re

from app.ats.schemas.resume import BilingualText, WorkExperienceItem

_RANGE_RE = re.compile(
    r"(?P<start>"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}[./]\d{2,4}"
    r"|\d{4}[./]\d{1,2}"
    r"|(?:19|20)\d{2}"
    r")"
    r"\s*[-–—]+\s*"
    r"(?P<end>"
    r"present|current|now|ongoing|დღემდე|მიმდინარე|დღეს"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}[./]\d{2,4}"
    r"|\d{4}[./]\d{1,2}"
    r"|(?:19|20)\d{2}"
    r")",
    re.IGNORECASE,
)

_ROLE_RE = re.compile(
    r"\b("
    r"designer|developer|engineer|manager|founder|director|lead|intern|analyst|consultant|"
    r"officer|architect|specialist|scientist|researcher|president|owner|partner|coordinator|"
    r"administrator|recruiter|programmer|head|ceo|cto|cfo|coo|vp|"
    r"დეველოპერ\w*|ინჟინერ\w*|მენეჯერ\w*|დირექტორ\w*|დამფუძნებ\w*|დიზაინერ\w*|"
    r"ანალიტიკ\w*|პროგრამისტ\w*|ხელმძღვანელ\w*|სპეციალისტ\w*"
    r")\b",
    re.IGNORECASE,
)
_ORG_RE = re.compile(
    r"\b(inc|llc|ltd|gmbh|corp|corporation|company|შპს|სს|ჯგუფი)\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"^(remote|hybrid|on-?site|tbilisi|თბილისი|batumi|ბათუმი|kutaisi|ქუთაისი|"
    r"georgia|საქართველო|london|berlin|paris|munich|amsterdam|warsaw|vienna|prague|"
    r"istanbul|yerevan|baku|new york|usa|uk|u\.s\.)$",
    re.IGNORECASE,
)
_EMPLOYMENT_RE = re.compile(
    r"^(full-?time|part-?time|contract|contractor|internship|freelance|permanent|temporary|"
    r"სრული განაკვეთი|ნახევარი განაკვეთი)$",
    re.IGNORECASE,
)
_PRESENT = {"present", "current", "now", "ongoing", "დღემდე", "მიმდინარე", "დღეს"}

_SECTION_ALIASES = {
    "experience": {
        "experience",
        "work experience",
        "employment",
        "work history",
        "professional experience",
        "career history",
        "employment history",
        "გამოცდილება",
        "სამუშაო გამოცდილება",
        "სამუშაო ისტორია",
    },
    "skip": {
        "summary",
        "profile",
        "about",
        "about me",
        "objective",
        "education",
        "academic background",
        "skills",
        "technical skills",
        "languages",
        "certifications",
        "certificates",
        "projects",
        "შეჯამება",
        "განათლება",
        "უნარები",
        "ენები",
        "სერტიფიკატები",
    },
}


def parse_experience_blocks(text: str) -> list[WorkExperienceItem]:
    """Read work history from the CV text and keep each role with its own employer."""
    body = _experience_text(text or "")
    roles: list[WorkExperienceItem] = []
    for block in _blocks(body):
        role = _role_from_block(block)
        if role is not None:
            roles.append(role)
    return roles


def swap_if_title_and_company_are_reversed(title: str, company: str) -> tuple[str, str]:
    """Swap only when the words themselves say the role and the employer were exchanged."""
    title_role = _is_role(title)
    company_role = _is_role(company)
    title_org = _is_org(title)
    company_org = _is_org(company)
    if company_role and not title_role:
        return company, title
    if title_org and not company_org and not title_role:
        return company, title
    return title, company


def _experience_text(text: str) -> str:
    current = "other"
    saw_experience = False
    kept: list[str] = []
    fallback: list[str] = []
    for line in text.splitlines():
        key = _section_key(line)
        if key:
            current = key
            if key == "experience":
                saw_experience = True
            continue
        if current == "experience":
            kept.append(line)
        elif current != "skip":
            fallback.append(line)
    return "\n".join(kept if saw_experience else fallback)


def _section_key(line: str) -> str:
    normalized = re.sub(r"^[#*\-\d\.\)\s]+", "", line.strip().lower()).strip(" :|-—–")
    if not normalized or len(normalized) > 48:
        return ""
    for key, names in _SECTION_ALIASES.items():
        if normalized in names:
            return key
    return ""


def _blocks(text: str) -> list[str]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    blocks: list[str] = []
    for chunk in chunks:
        blocks.extend(_split_roles(chunk))
    return blocks


def _split_roles(chunk: str) -> list[str]:
    lines = chunk.splitlines()
    groups: list[list[str]] = []
    current: list[str] = []
    seen_date = False
    seen_body = False
    for line in lines:
        stripped = line.strip()
        if seen_body and stripped and _starts_new_role(stripped):
            groups.append(current)
            current = [line]
            seen_date = bool(_RANGE_RE.search(stripped))
            seen_body = False
            continue
        current.append(line)
        if not stripped:
            continue
        if _RANGE_RE.search(stripped):
            if seen_date and seen_body:
                groups.append(current[:-1])
                current = [line]
                seen_body = False
            seen_date = True
        elif seen_date and not _is_meta_line(stripped):
            seen_body = True
    if any(line.strip() for line in current):
        groups.append(current)
    return ["\n".join(group).strip() for group in groups if any(line.strip() for line in group)]


def _starts_new_role(line: str) -> bool:
    if line.startswith(("•", "-", "*", "–")):
        return False
    if len(line) > 80:
        return False
    return _is_role(line) or ("|" in line and _RANGE_RE.search(line))


def _role_from_block(block: str) -> WorkExperienceItem | None:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return None
    header: list[str] = []
    index = 0
    while index < len(lines) and len(header) < 5:
        line = lines[index]
        if header and _header_has_date(header) and not _is_meta_line(line):
            break
        if not header and len(line) > 110:
            break
        header.append(line)
        index += 1
    body = lines[index:]
    segments: list[str] = []
    for line in header:
        segments.extend(_segments(line))
    title, company, location, employment, start, end = _assign(segments)
    if not title and not company and not start:
        return None
    description = "\n".join(body).strip()
    return WorkExperienceItem(
        title=_same(title),
        company=_same(company),
        location=_same(location),
        employment_type=employment,
        description=_same(description),
        start_date=start,
        end_date=end,
        is_current=bool(end and end.casefold() in _PRESENT),
    )


def _header_has_date(lines: list[str]) -> bool:
    return any(_RANGE_RE.search(line) for line in lines)


def _is_meta_line(line: str) -> bool:
    if _RANGE_RE.search(line) or _is_location(line) or _is_employment(line):
        return True
    if len(line) > 70:
        return False
    return _is_role(line) or _is_org(line) or "|" in line or "—" in line or "–" in line


def _segments(line: str) -> list[str]:
    match = _RANGE_RE.search(line)
    if not match:
        return _split_labels(line)
    pieces: list[str] = []
    before = line[: match.start()].strip(" |,•-—–")
    after = line[match.end() :].strip(" |,•-—–")
    if before:
        pieces.extend(_split_labels(before))
    pieces.append(match.group(0).strip())
    if after:
        pieces.extend(_split_labels(after))
    return [piece for piece in pieces if piece]


def _split_labels(text: str) -> list[str]:
    parts = re.split(r"\s*\|\s*|\s+[—–]\s+|\s+@\s+|\s+\bat\b\s+", text)
    labels: list[str] = []
    for part in parts:
        part = part.strip(" ,")
        if not part:
            continue
        if "," in part:
            left, right = [piece.strip() for piece in part.split(",", 1)]
            if left and _is_location(right):
                labels.extend([left, right])
                continue
        labels.append(part)
    return labels


def _assign(segments: list[str]) -> tuple[str, str, str, str, str | None, str | None]:
    labels: list[str] = []
    location = ""
    employment = ""
    start = end = None
    for segment in segments:
        match = _RANGE_RE.search(segment)
        if match and match.group(0).strip() == segment.strip():
            start = start or match.group("start").strip()
            end = end or match.group("end").strip()
            continue
        if _is_employment(segment) and not employment:
            employment = segment.strip()
            continue
        if _is_location(segment) and not location:
            location = segment.strip()
            continue
        labels.append(segment.strip())
    roles = [label for label in labels if _is_role(label)]
    orgs = [label for label in labels if label not in roles]
    title = roles[0] if roles else ""
    company = orgs[0] if orgs else ""
    if not title and not company and len(labels) == 1:
        company = labels[0]
    elif not title and not company and len(labels) >= 2:
        title, company = labels[0], labels[1]
        title, company = swap_if_title_and_company_are_reversed(title, company)
    return title, company, location, employment, start, end


def _is_role(text: str) -> bool:
    return bool(text and _ROLE_RE.search(text) and not _is_org(text))


def _is_org(text: str) -> bool:
    return bool(text and _ORG_RE.search(text))


def _is_location(text: str) -> bool:
    return bool(text and _LOCATION_RE.fullmatch(text.strip()))


def _is_employment(text: str) -> bool:
    return bool(text and _EMPLOYMENT_RE.fullmatch(text.strip()))


def _same(text: str) -> BilingualText:
    cleaned = (text or "").strip()
    return BilingualText(en=cleaned, ka=cleaned)
