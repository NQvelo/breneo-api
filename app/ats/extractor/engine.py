"""AI resume extraction. Incomplete model output is rejected."""

from __future__ import annotations

import logging

from app.ats.exceptions import (
    AiUnavailable,
    IncompleteResumeError,
    LlmExtractionFailed,
    LlmNotConfigured,
)
from app.ats.extractor.llm import extract_with_llm
from app.ats.schemas.resume import ResumeData, missing_fields
from app.ats.textutil import detect_language

logger = logging.getLogger(__name__)


def extract_resume(text: str, filename: str = "") -> ResumeData:
    """Parse resume text with Groq (or OpenAI) and require every CV field."""
    try:
        resume = extract_with_llm(text)
    except LlmNotConfigured as exc:
        raise AiUnavailable(
            "Resume parsing needs GROQ_API_KEY. Add a free Groq key and upload the CV again."
        ) from exc
    except (LlmExtractionFailed, Exception) as exc:
        logger.exception("AI resume extraction failed")
        raise AiUnavailable("The AI could not parse this resume. Try the upload again.") from exc

    missing = missing_fields(resume)
    if missing:
        try:
            resume = extract_with_llm(text, missing=missing)
        except (LlmNotConfigured, LlmExtractionFailed, Exception) as exc:
            logger.exception("AI resume repair failed")
            raise AiUnavailable("The AI could not fill every resume field. Try the upload again.") from exc
        missing = missing_fields(resume)
    if missing:
        raise IncompleteResumeError(missing)

    if resume.language == "unknown":
        resume.language = detect_language(text)
    resume.extraction_method = "llm"
    resume.source_filename = filename or resume.source_filename
    return resume
