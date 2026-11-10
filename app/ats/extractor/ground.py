"""Replace rewritten job text with the wording that is actually in the CV."""

from __future__ import annotations

import re

from app.ats.extractor.heuristic import _match_header
from app.ats.schemas.resume import BilingualText, ResumeData

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


def ground_resume(resume: ResumeData, source: str) -> ResumeData:
    """Snap companies, descriptions, schools, and dates back to the source text."""
    text = source or ""
    if not text.strip():
        return resume
    for role in resume.work_experience:
        _ground_role(role, text)
    for school in resume.education:
        _ground_school(school, text)
    snapped = _snap_bilingual(resume.summary, text)
    if snapped:
        resume.summary = snapped
    return resume


def _ground_role(role, source: str) -> None:
    company = _text_of(role.company)
    title = _text_of(role.title)
    header = _find_header(source, company, title)
    block = _body_after(source, header) if header else ""
    if header:
        role.company = _verbatim(_company_from_header(header, company))
        role.title = _verbatim(_title_from_header(header, title, _text_of(role.company)))
        start, end = _dates_on(header)
        if start:
            role.start_date = start
        if end:
            role.end_date = end
            if end.casefold() in {"present", "current", "now", "ongoing", "დღემდე", "მიმდინარე", "დღეს"}:
                role.is_current = True
    if block and not _contains(block, _text_of(role.description)):
        role.description = _verbatim(block)
    else:
        snapped = _snap_bilingual(role.description, source)
        if snapped:
            role.description = snapped
    if not header:
        snapped_company = _snap_bilingual(role.company, source)
        if snapped_company:
            role.company = snapped_company
        snapped_title = _snap_bilingual(role.title, source)
        if snapped_title:
            role.title = snapped_title


def _ground_school(school, source: str) -> None:
    name = _text_of(school.school)
    header = _find_header(source, name, _text_of(school.degree))
    if header:
        school.school = _verbatim(_company_from_header(header, name))
        start, end = _dates_on(header)
        if start:
            school.start_date = start
        if end:
            school.end_date = end
            if end.casefold() in {"present", "current", "now", "ongoing", "დღემდე", "მიმდინარე", "დღეს"}:
                school.is_current = True
        degree = _title_from_header(header, _text_of(school.degree), _text_of(school.school))
        if degree:
            school.degree = _verbatim(degree)
    else:
        snapped = _snap_bilingual(school.school, source)
        if snapped:
            school.school = snapped
    field = _snap_bilingual(school.field_of_study, source)
    if field:
        school.field_of_study = field


def _find_header(source: str, *needles: str) -> str:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    for needle in needles:
        tokens = _tokens(needle)
        if not tokens:
            continue
        for line in lines:
            if _contains(line, needle):
                return line
        best = ""
        best_hits = 0
        for line in lines:
            if len(line) > 160:
                continue
            hits = sum(1 for token in tokens if token.casefold() in line.casefold())
            if hits > best_hits:
                best, best_hits = line, hits
        if best and best_hits >= 1:
            return best
    return ""


def _company_from_header(header: str, model_company: str) -> str:
    remainder, _start, _end = _split_range(header)
    exact = _exact_slice(remainder, model_company) or _exact_slice(header, model_company)
    if exact:
        return exact
    segments = [part.strip() for part in re.split(r"\s*\|\s*", remainder) if part.strip()]
    tokens = _tokens(model_company)
    best = ""
    best_hits = 0
    for segment in segments:
        hits = sum(1 for token in tokens if token.casefold() in segment.casefold())
        if hits > best_hits:
            best, best_hits = segment, hits
    if best and best_hits:
        return best
    return model_company.strip()


def _title_from_header(header: str, model_title: str, company: str) -> str:
    remainder, _start, _end = _split_range(header)
    exact = _exact_slice(remainder, model_title)
    if exact:
        return exact
    if company and company in remainder:
        leftover = remainder.replace(company, " ", 1)
        leftover = re.sub(r"\s*[|@]\s*", " ", leftover)
        leftover = " ".join(leftover.split())
        if leftover and leftover.casefold() != company.casefold():
            return leftover
    return model_title.strip()


def _body_after(source: str, header: str) -> str:
    lines = source.splitlines()
    target = header.strip()
    for index, line in enumerate(lines):
        if line.strip() != target:
            continue
        body: list[str] = []
        for follow in lines[index + 1 :]:
            stripped = follow.strip()
            if not stripped:
                if body:
                    break
                continue
            if _match_header(stripped):
                break
            if body and _RANGE_RE.search(stripped) and len(stripped) < 80:
                break
            body.append(stripped)
        return "\n".join(body).strip()
    return ""


def _dates_on(header: str) -> tuple[str | None, str | None]:
    _remainder, start, end = _split_range(header)
    return start, end


def _split_range(text: str) -> tuple[str, str | None, str | None]:
    match = _RANGE_RE.search(text or "")
    if not match:
        return text, None, None
    start = match.group("start").strip()
    end = match.group("end").strip()
    remainder = (text[: match.start()] + text[match.end() :]).strip(" |")
    return remainder, start, end


def _snap_bilingual(value: BilingualText, source: str) -> BilingualText | None:
    for candidate in (_text_of(value), value.en, value.ka):
        exact = _exact_slice(source, candidate)
        if exact:
            return _verbatim(exact)
    return None


def _verbatim(text: str) -> BilingualText:
    cleaned = (text or "").strip()
    return BilingualText(en=cleaned, ka=cleaned)


def _text_of(value: BilingualText | None) -> str:
    if value is None:
        return ""
    return (value.en or "").strip() or (value.ka or "").strip()


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[\w\u10A0-\u10FF]+", text or "") if len(token) >= 3]


def _contains(haystack: str, needle: str) -> bool:
    return _exact_slice(haystack, needle) is not None


def _exact_slice(source: str, needle: str) -> str | None:
    needle = (needle or "").strip()
    if len(needle) < 2 or not source:
        return None
    folded = source.casefold()
    direct = folded.find(needle.casefold())
    if direct >= 0:
        return source[direct : direct + len(needle)].strip()
    compact_source, indexes = _compact(source)
    compact_needle, _unused = _compact(needle)
    if len(compact_needle) < 2:
        return None
    found = compact_source.casefold().find(compact_needle.casefold())
    if found < 0:
        return None
    start = indexes[found]
    end = indexes[found + len(compact_needle) - 1] + 1
    return source[start:end].strip()


def _compact(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    indexes: list[int] = []
    previous_space = False
    for index, char in enumerate(text):
        if char.isspace():
            if previous_space or not chars:
                continue
            chars.append(" ")
            indexes.append(index)
            previous_space = True
            continue
        previous_space = False
        chars.append(char)
        indexes.append(index)
    return "".join(chars), indexes
