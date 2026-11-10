"""Turn resume text into JSON by sending it to the language model."""

from __future__ import annotations

from app.ats.extractor.llm import extract_with_llm
from app.ats.schemas.resume import ResumeData


def extract_resume(text: str, filename: str = "") -> ResumeData:
    """Send the resume's plain text to the model and return its JSON."""
    resume = extract_with_llm(text)
    resume.source_filename = filename or resume.source_filename
    resume.extraction_method = "llm"
    return resume
