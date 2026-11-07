"""Choose the LLM extractor, and fall back to the section parser."""

from __future__ import annotations

import logging

from app.ats.exceptions import LlmExtractionFailed, LlmNotConfigured
from app.ats.extractor.heuristic import extract_with_heuristics
from app.ats.extractor.llm import extract_with_llm
from app.ats.schemas.resume import ResumeData
from app.ats.textutil import detect_language

logger = logging.getLogger(__name__)


def extract_resume(text: str, filename: str = "") -> ResumeData:
    """Turn cleaned resume text into ``ResumeData``.

    A missing API key or a bad model response does not fail the request.
    The heuristic parser still returns skills, dates, and contact fields.
    """
    warnings: list[str] = []
    try:
        resume = extract_with_llm(text)
    except LlmNotConfigured:
        warnings.append("llm_not_configured")
        resume = extract_with_heuristics(text, filename=filename)
    except LlmExtractionFailed as exc:
        logger.warning("LLM resume extraction failed (%s); using the section parser", exc)
        warnings.append("llm_failed")
        resume = extract_with_heuristics(text, filename=filename)
    except Exception:
        logger.exception("LLM resume extraction failed; using the section parser")
        warnings.append("llm_failed")
        resume = extract_with_heuristics(text, filename=filename)

    if resume.language == "unknown":
        resume.language = detect_language(text)
    resume.source_filename = filename or resume.source_filename
    resume.warnings = list(dict.fromkeys([*resume.warnings, *warnings]))
    return resume
