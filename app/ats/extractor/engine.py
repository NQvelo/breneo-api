"""Entry points for the layout pipeline.

The model is only asked to validate a resume after pages, columns, and
experience blocks have already been reconstructed.
"""

from __future__ import annotations

from app.ats.extractor.llm import extract_with_llm
from app.ats.pipeline.engine import parse_bytes, parse_text
from app.ats.schemas.resume import ResumeData


def extract_resume(text: str, filename: str = "") -> ResumeData:
    """Parse resume text that already has a logical reading order."""
    return parse_text(text, filename, extract_with_llm)


def parse_file(data: bytes, filename: str) -> tuple[ResumeData, str]:
    """Parse uploaded bytes without flattening the document first."""
    return parse_bytes(data, filename, extract_with_llm)
