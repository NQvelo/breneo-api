"""Run the layout pipeline, then let the model validate only what the blocks support."""

from __future__ import annotations

import logging

from app.ats.exceptions import EmptyResumeError, LlmExtractionFailed, LlmNotConfigured
from app.ats.pipeline.read import document_from_text, load_document
from app.ats.pipeline.structure import build_resume
from app.ats.schemas.resume import ResumeData
from app.ats.textutil import detect_language, meaningful_count

logger = logging.getLogger(__name__)


def parse_bytes(data: bytes, filename: str, ai) -> tuple[ResumeData, str]:
    document = load_document(data, filename)
    resume = _assemble(document.ordered_text(), document.filename, document.method, document.page_count, document.warnings, ai)
    return resume, document.ordered_text()


def parse_text(text: str, filename: str, ai) -> ResumeData:
    document = document_from_text(text, filename)
    if meaningful_count(document.ordered_text()) < 20:
        raise EmptyResumeError(
            "The file was read, but no candidate details could be extracted. "
            "Upload a clearer PDF, Word file, or image."
        )
    return _assemble(document.ordered_text(), filename, "text", 1, [], ai)


def _assemble(text: str, filename: str, method: str, pages: int, warnings: list[str], ai) -> ResumeData:
    resume = build_resume(text, filename)
    resume.parser_method = method
    resume.warnings = list(warnings)
    used = [method, "layout", "blocks"]
    try:
        suggested = ai(text)
    except LlmNotConfigured:
        resume.warnings.append("llm_not_configured")
        used.append("heuristic")
        suggested = None
    except (LlmExtractionFailed, Exception):
        logger.exception("Resume validation model failed")
        resume.warnings.append("llm_failed")
        used.append("heuristic")
        suggested = None
    if suggested is not None:
        _fill_gaps(resume, suggested, text)
        resume.extraction_method = "llm"
        used.append("llm")
    else:
        resume.extraction_method = "heuristic"
    if resume.language == "unknown":
        resume.language = detect_language(text)
    resume.source_filename = filename or resume.source_filename
    resume.warnings = list(dict.fromkeys([*resume.warnings, *_gaps(resume)]))
    if not _has_facts(resume):
        raise EmptyResumeError(
            "The file was read, but no candidate details could be extracted. "
            "Upload a clearer PDF, Word file, or image."
        )
    resume.parsing_metadata = {
        "extraction_methods_used": used,
        "pages_processed": pages,
        "document_quality": resume.kind if False else ("readable" if len(_gaps(resume)) < 3 else "partial"),
        "overall_confidence": _confidence(resume),
        "warnings": list(resume.warnings),
    }
    return resume


def _fill_gaps(resume: ResumeData, suggested: ResumeData, source: str) -> None:
    """Accept a model value only when that exact text is in the document and the block left it empty."""
    folded = source.casefold()
    if not (resume.email or "") and suggested.email and suggested.email.casefold() in folded:
        resume.email = suggested.email
    if not (resume.phone or "") and suggested.phone and _compact(suggested.phone) in _compact(source):
        resume.phone = suggested.phone
    if resume.summary.is_empty() and _in_source(suggested.summary.en or suggested.summary.ka, source):
        resume.summary = suggested.summary
    if resume.headline.is_empty() and _in_source(suggested.headline.en or suggested.headline.ka, source):
        resume.headline = suggested.headline
    if not resume.skills:
        resume.skills = [skill for skill in suggested.skills if _in_source(skill.name_en or skill.name_ka, source)]
    if not resume.work_experience:
        resume.work_experience = [
            job
            for job in suggested.work_experience
            if _in_source(job.title.en or job.title.ka, source) or _in_source(job.company.en or job.company.ka, source)
        ]
    else:
        for job, extra in zip(resume.work_experience, suggested.work_experience):
            if job.description.is_empty() and _in_source(extra.description.en or extra.description.ka, source):
                job.description = extra.description
            if (job.company.en or job.company.ka) == "" and _in_source(extra.company.en or extra.company.ka, source):
                job.company = extra.company
            if (job.title.en or job.title.ka) == "" and _in_source(extra.title.en or extra.title.ka, source):
                job.title = extra.title
    if not resume.education:
        resume.education = [
            school
            for school in suggested.education
            if _in_source(school.school.en or school.school.ka, source) or _in_source(school.degree.en or school.degree.ka, source)
        ]


def _in_source(value: str, source: str) -> bool:
    cleaned = (value or "").strip()
    return len(cleaned) >= 2 and cleaned.casefold() in source.casefold()


def _compact(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit() or ch == "+")


def _gaps(resume: ResumeData) -> list[str]:
    notes = []
    if resume.full_name.is_empty():
        notes.append("missing_full_name")
    if not resume.email:
        notes.append("missing_email")
    if not resume.phone:
        notes.append("missing_phone")
    if not resume.work_experience:
        notes.append("missing_work_experience")
    for index, job in enumerate(resume.work_experience):
        if job.title.is_empty():
            notes.append(f"experience_{index + 1}_missing_role")
        if job.company.is_empty():
            notes.append(f"experience_{index + 1}_missing_company")
    return notes


def _has_facts(resume: ResumeData) -> bool:
    return bool(
        not resume.full_name.is_empty()
        or resume.email
        or resume.phone
        or resume.skills
        or resume.work_experience
        or resume.education
        or not resume.summary.is_empty()
    )


def _confidence(resume: ResumeData) -> float:
    checks = [
        not resume.full_name.is_empty(),
        bool(resume.email),
        bool(resume.work_experience),
        all(not job.title.is_empty() and not job.company.is_empty() for job in resume.work_experience) if resume.work_experience else False,
        bool(resume.education) or bool(resume.skills),
    ]
    return round(sum(1 for item in checks if item) / len(checks), 2)
