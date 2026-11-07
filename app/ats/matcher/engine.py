"""ATS score: keyword overlap, experience weight, and TF-IDF similarity."""

from __future__ import annotations

import logging
import re
from datetime import date

from app.ats.matcher.text import normalize_token, token_set, tokenize
from app.ats.schemas.match import MatchResult, MatchWeights, ScoreBreakdown
from app.ats.schemas.resume import ResumeData
from app.ats.textutil import detect_language

logger = logging.getLogger(__name__)

WEIGHTS = MatchWeights()
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_REQUIREMENT_RE = re.compile(
    r"(?<!\d)(\d{1,2}(?:[.,]\d)?)\s*\+?\s*(?:years|yrs|year|წლიანი|წლის|წელი|წელიწადი)",
    re.IGNORECASE,
)
_PRESENT_RE = re.compile(r"(present|current|now|ongoing|დღემდე|მიმდინარე)", re.IGNORECASE)
_MAX_KEYWORDS = 30


def score_resume(
    resume: ResumeData,
    job_text: str,
    *,
    job_title: str = "",
    required_skills: list[str] | None = None,
    source_text: str = "",
) -> MatchResult:
    """Compare a parsed resume with a job description in English or Georgian."""
    skills = [skill.strip() for skill in (required_skills or []) if skill and skill.strip()]
    job_blob = "\n".join(part for part in (job_title, job_text, ", ".join(skills)) if part)
    resume_blob = "\n".join(
        part for part in (source_text, resume.to_match_text()) if part and part.strip()
    )
    keywords = _job_keywords(job_text, job_title, skills)
    resume_tokens = token_set(resume_blob)
    matched, missing = _overlap(keywords, resume_tokens, resume_blob)
    keyword_score = _keyword_score(keywords, matched)

    candidate_years = _candidate_years(resume, source_text)
    required_years = _required_years(job_blob)
    title_coverage = _title_coverage(job_title, resume)
    experience_score = _experience_score(candidate_years, required_years, title_coverage)
    semantic_score = _semantic_similarity(resume_blob, job_blob)

    if not keywords:
        keyword_score = semantic_score

    overall = round(
        WEIGHTS.keyword_overlap * keyword_score
        + WEIGHTS.experience * experience_score
        + WEIGHTS.semantic_similarity * semantic_score,
        2,
    )
    job_language = detect_language(job_blob)
    recommendations = _recommendations(
        missing=missing,
        candidate_years=candidate_years,
        required_years=required_years,
        title_coverage=title_coverage,
        semantic_score=semantic_score,
        job_language=job_language,
        resume_language=resume.language,
        job_title=job_title,
        keyword_count=len(keywords),
    )
    return MatchResult(
        scores=ScoreBreakdown(
            keyword_overlap=round(keyword_score, 2),
            experience=round(experience_score, 2),
            semantic_similarity=round(semantic_score, 2),
            overall=overall,
        ),
        weights=WEIGHTS,
        matched_keywords=matched,
        missing_keywords=missing,
        candidate_years_experience=candidate_years,
        required_years_experience=required_years,
        resume_language=resume.language,
        job_language=job_language,
        recommendations=recommendations,
    )


def _job_keywords(job_text: str, job_title: str, required_skills: list[str]) -> list[tuple[str, str, int]]:
    """Return (normalized, display, weight) keywords, skills first."""
    chosen: list[tuple[str, str, int]] = []
    seen: set[str] = set()

    def add(display: str, weight: int) -> None:
        normalized = normalize_token(display)
        if not normalized or normalized in seen or len(normalized) < 2:
            return
        if normalized.isdigit():
            return
        seen.add(normalized)
        chosen.append((normalized, display.strip(), weight))

    for skill in required_skills:
        add(skill, 2)
    for token in tokenize(job_title):
        add(token, 2)
    for token in tokenize(job_text):
        add(token, 1)
        if len(chosen) >= _MAX_KEYWORDS:
            break
    return chosen[:_MAX_KEYWORDS]


def _overlap(
    keywords: list[tuple[str, str, int]],
    resume_tokens: set[str],
    resume_blob: str,
) -> tuple[list[str], list[str]]:
    blob = " ".join(tokenize(resume_blob))
    matched: list[str] = []
    missing: list[str] = []
    for normalized, display, _weight in keywords:
        phrase = " ".join(tokenize(display))
        if normalized in resume_tokens or (phrase and phrase in blob):
            matched.append(display)
        else:
            missing.append(display)
    return matched, missing


def _keyword_score(keywords: list[tuple[str, str, int]], matched_display: list[str]) -> float:
    if not keywords:
        return 0.0
    matched_keys = {normalize_token(item) for item in matched_display}
    total = 0
    got = 0
    for normalized, _display, weight in keywords:
        total += weight
        if normalized in matched_keys:
            got += weight
    if total == 0:
        return 0.0
    return 100.0 * got / total


def _year_of(value: str | None) -> int | None:
    if not value:
        return None
    match = _YEAR_RE.search(value)
    if not match:
        return None
    return int(match.group(0))


def _candidate_years(resume: ResumeData, source_text: str) -> float:
    today = date.today().year
    intervals: list[tuple[int, int]] = []
    for role in resume.work_experience:
        start = _year_of(role.start_date)
        end = _year_of(role.end_date)
        ongoing = role.is_current or bool(role.end_date and _PRESENT_RE.search(role.end_date))
        if ongoing or (start and end is None and role.is_current):
            end = today
        if start is None:
            continue
        if end is None:
            end = start
        if end < start:
            continue
        intervals.append((start, end))
    if not intervals and source_text:
        years = [int(year) for year in _YEAR_RE.findall(source_text)]
        if len(years) >= 2:
            start, end = min(years), max(years)
            if end >= start:
                intervals.append((start, end))
    if not intervals:
        return 0.0
    intervals.sort()
    merged: list[list[int]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    total = 0.0
    for start, end in merged:
        total += 0.5 if end == start else float(end - start)
    return round(min(total, 45.0), 1)


def _required_years(job_text: str) -> float | None:
    found = []
    for match in _REQUIREMENT_RE.finditer(job_text or ""):
        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if 0 < value <= 40:
            found.append(value)
    if not found:
        return None
    return max(found)


def _title_coverage(job_title: str, resume: ResumeData) -> float:
    title_tokens = token_set(job_title)
    if not title_tokens:
        return 50.0
    role_text = " ".join(
        " ".join(part for part in (role.title.en, role.title.ka, role.description.en, role.description.ka) if part)
        for role in resume.work_experience
    )
    role_tokens = token_set(role_text)
    if not role_tokens:
        return 0.0
    hit = len(title_tokens & role_tokens)
    return 100.0 * hit / len(title_tokens)


def _experience_score(candidate_years: float, required_years: float | None, title_coverage: float) -> float:
    if required_years:
        years_score = min(100.0, (candidate_years / required_years) * 100.0)
    elif candidate_years > 0:
        years_score = min(100.0, 55.0 + candidate_years * 5.0)
    else:
        years_score = 35.0
    return 0.7 * years_score + 0.3 * title_coverage


def _semantic_similarity(resume_text: str, job_text: str) -> float:
    left = (resume_text or "").strip()
    right = (job_text or "").strip()
    if not left or not right:
        return 0.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        logger.exception("scikit-learn is required for ATS semantic similarity")
        return 0.0

    def _cosine(vectorizer) -> float:
        try:
            matrix = vectorizer.fit_transform([left, right])
        except ValueError:
            return 0.0
        score = cosine_similarity(matrix[0], matrix[1])[0][0]
        if score != score:  # NaN
            return 0.0
        return float(max(0.0, min(1.0, score)))

    word_score = _cosine(TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=1))
    char_score = _cosine(TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1))
    return ((word_score + char_score) / 2.0) * 100.0


def _recommendations(
    *,
    missing: list[str],
    candidate_years: float,
    required_years: float | None,
    title_coverage: float,
    semantic_score: float,
    job_language: str,
    resume_language: str,
    job_title: str,
    keyword_count: int,
) -> list[str]:
    georgian = job_language == "ka"
    notes: list[str] = []
    if keyword_count == 0:
        notes.append(
            "ვაკანსიის ტექსტი ძალიან მოკლეა საკვანძო სიტყვების ამოსაღებად."
            if georgian
            else "The job description is too short to extract keywords. Add required skills."
        )
    if missing:
        shown = ", ".join(missing[:8])
        notes.append(
            f"რეზიუმეს აკლია ვაკანსიის საკვანძო სიტყვები: {shown}."
            if georgian
            else f"Add the missing job keywords to the resume: {shown}."
        )
    if required_years is not None and candidate_years + 0.2 < required_years:
        notes.append(
            f"გამოცდილება (~{candidate_years:g} წელი) ნაკლებია მოთხოვნილ {required_years:g} წელზე."
            if georgian
            else f"Experience (~{candidate_years:g} years) is below the requested {required_years:g} years."
        )
    if job_title and title_coverage < 40:
        notes.append(
            "თანამდებობის სათაური სუსტად ემთხვევა ვაკანსიის სათაურს. დააზუსტეთ როლი შეჯამებაში."
            if georgian
            else "The role titles only weakly match the job title. Mirror the job title in the summary."
        )
    if semantic_score < 45:
        notes.append(
            "რეზიუმის ფორმულირება შორსაა ვაკანსიის ტექსტისგან. გამოიყენეთ იგივე ტერმინები."
            if georgian
            else "The resume wording is distant from the job description. Reuse the job's terminology."
        )
    if job_language == "ka" and resume_language == "en":
        notes.append("ვაკანსია ქართულადაა. დაამატეთ უნარებისა და თანამდებობების ქართული დასახელებები.")
    elif job_language == "en" and resume_language == "ka":
        notes.append(
            "The job description is in English. Add English titles and skill names next to the Georgian text."
        )
    if not notes:
        notes.append(
            "რეზიუმე კარგად ემთხვევა ვაკანსიას. შეინარჩუნეთ იგივე ტერმინები."
            if georgian
            else "The resume aligns well with this job. Keep the same terminology in the summary."
        )
    return notes[:6]
