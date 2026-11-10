"""AI resume extraction, with a text fallback when the model misses facts."""

from __future__ import annotations

import logging
import re

from app.ats.exceptions import EmptyResumeError, LlmExtractionFailed, LlmNotConfigured
from app.ats.extractor.ground import ground_resume
from app.ats.extractor.heuristic import extract_with_heuristics
from app.ats.extractor.llm import extract_with_llm
from app.ats.schemas.resume import ResumeData, fill_blank_translations

logger = logging.getLogger(__name__)

_LINK_RE = re.compile(
    r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+|(?:linkedin|github|behance|dribbble)\.com/[^\s<>\"']+)",
    re.IGNORECASE,
)


def extract_resume(text: str, filename: str = "") -> ResumeData:
    """Parse resume text. A partial CV is returned with warnings instead of an error."""
    resume, from_model = _from_model(text, filename)
    resume = fill_blank_translations(resume)
    if from_model and not _has_facts(resume):
        resume = _repair(resume, text)
    resume = ground_resume(resume, text)
    resume = _recover_gaps(resume, text)
    resume = ground_resume(resume, text)
    resume = fill_blank_translations(resume)
    if not _has_facts(resume):
        raise EmptyResumeError(
            "The file was read, but no candidate details could be extracted. "
            "Upload a clearer PDF, Word file, or image."
        )
    resume.warnings = list(dict.fromkeys([*resume.warnings, *_coverage_warnings(resume)]))
    if resume.language == "unknown":
        from app.ats.textutil import detect_language

        resume.language = detect_language(text)
    resume.source_filename = filename or resume.source_filename
    resume.parsing_metadata = {
        "extraction_methods_used": _methods_used(resume),
        "document_quality": _document_quality(resume),
        "overall_confidence": _confidence(resume),
        "warnings": list(resume.warnings),
    }
    return resume


def _from_model(text: str, filename: str) -> tuple[ResumeData, bool]:
    try:
        resume = extract_with_llm(text)
    except LlmNotConfigured:
        logger.warning("Resume AI is not configured; using the text parser")
        resume = extract_with_heuristics(text, filename)
        resume.warnings.append("llm_not_configured")
        return resume, False
    except (LlmExtractionFailed, Exception):
        logger.exception("AI resume extraction failed; using the text parser")
        resume = extract_with_heuristics(text, filename)
        resume.warnings.append("llm_failed")
        return resume, False
    resume.extraction_method = "llm"
    resume.source_filename = filename or resume.source_filename
    return resume, True


def _repair(resume: ResumeData, text: str) -> ResumeData:
    try:
        repaired = fill_blank_translations(extract_with_llm(text))
    except (LlmNotConfigured, LlmExtractionFailed, Exception):
        logger.exception("AI resume repair failed")
        resume.warnings.append("llm_repair_failed")
        return resume
    if _has_facts(repaired):
        repaired.warnings = list(dict.fromkeys([*resume.warnings, *repaired.warnings]))
        repaired.extraction_method = "llm"
        return repaired
    resume.warnings.append("llm_repair_empty")
    return resume


def _recover_gaps(resume: ResumeData, text: str) -> ResumeData:
    """Fill facts the model left empty when they are still visible in the source text."""
    found = extract_with_heuristics(text or "")
    recovered: list[str] = []
    if resume.full_name.is_empty() and not found.full_name.is_empty():
        resume.full_name = found.full_name
        recovered.append("full_name")
    if not (resume.email or "").strip() and found.email:
        resume.email = found.email
        recovered.append("email")
    if not (resume.phone or "").strip() and found.phone:
        resume.phone = found.phone
        recovered.append("phone")
    if resume.headline.is_empty() and not found.headline.is_empty():
        resume.headline = found.headline
        recovered.append("headline")
    if resume.summary.is_empty() and not found.summary.is_empty():
        resume.summary = found.summary
        recovered.append("summary")
    if not resume.skills and found.skills:
        resume.skills = found.skills
        recovered.append("skills")
    if not resume.work_experience and found.work_experience:
        resume.work_experience = found.work_experience
        recovered.append("work_experience")
    if not resume.education and found.education:
        resume.education = found.education
        recovered.append("education")
    if not resume.certifications and found.certifications:
        resume.certifications = found.certifications
        recovered.append("certifications")
    if not resume.languages and found.languages:
        resume.languages = found.languages
        recovered.append("languages")
    links = list(resume.links)
    for link in _links_in(text):
        if link not in links:
            links.append(link)
    if links != list(resume.links):
        resume.links = links
        recovered.append("links")
    if recovered:
        resume.warnings.append("recovered:" + ",".join(recovered))
    return resume


def _links_in(text: str) -> list[str]:
    found = []
    for match in _LINK_RE.findall(text or ""):
        link = match.rstrip(".,);")
        if link not in found:
            found.append(link)
    return found


def _has_facts(resume: ResumeData) -> bool:
    return bool(
        not resume.full_name.is_empty()
        or resume.email
        or resume.phone
        or not resume.headline.is_empty()
        or not resume.summary.is_empty()
        or resume.skills
        or resume.work_experience
        or resume.education
        or resume.projects
        or resume.links
    )


def _coverage_warnings(resume: ResumeData) -> list[str]:
    notes = []
    if resume.full_name.is_empty():
        notes.append("missing_full_name")
    if not resume.email:
        notes.append("missing_email")
    if not resume.phone:
        notes.append("missing_phone")
    if not resume.work_experience:
        notes.append("missing_work_experience")
    if not resume.education:
        notes.append("missing_education")
    if not resume.skills:
        notes.append("missing_skills")
    return notes


def _methods_used(resume: ResumeData) -> list[str]:
    methods = []
    if resume.parser_method:
        methods.append(resume.parser_method)
    methods.append(resume.extraction_method or "heuristic")
    if any(item.startswith("recovered:") for item in resume.warnings):
        methods.append("text_recovery")
    return methods


def _document_quality(resume: ResumeData) -> str:
    if "llm_failed" in resume.warnings or "llm_not_configured" in resume.warnings:
        return "text_only"
    missing = [item for item in resume.warnings if item.startswith("missing_")]
    if len(missing) >= 3:
        return "partial"
    return "readable"


def _confidence(resume: ResumeData) -> float:
    checks = [
        not resume.full_name.is_empty(),
        bool(resume.email),
        bool(resume.phone),
        bool(resume.skills),
        bool(resume.work_experience),
        bool(resume.education),
        not resume.summary.is_empty(),
    ]
    score = sum(1 for item in checks if item) / len(checks)
    if "llm_failed" in resume.warnings or "llm_not_configured" in resume.warnings:
        score *= 0.8
    return round(score, 2)
