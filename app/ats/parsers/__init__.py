"""Dispatch resume bytes to the PDF or DOCX parser."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.ats.exceptions import EmptyResumeError, UnsupportedResumeFormat
from app.ats.parsers.docx import extract_docx
from app.ats.parsers.pdf import extract_pdf


@dataclass
class ParsedDocument:
    text: str
    method: str
    page_count: int = 1
    warnings: list[str] = field(default_factory=list)
    filename: str = ""


def read_resume(data: bytes, filename: str) -> ParsedDocument:
    """Read a resume file into cleaned plain text.

    Raises a ``ResumeReaderError`` subclass for corrupt, locked, empty,
    or unsupported files. Those errors are meant to be returned as HTTP
    responses and must not take down the request worker.
    """
    if not data:
        raise EmptyResumeError("The uploaded file is empty.")
    resolved_name = _resolve_filename(data, filename or "")
    extension = os.path.splitext(resolved_name)[1].lower()
    if extension == ".pdf":
        text, method, page_count, warnings = extract_pdf(data)
        return ParsedDocument(
            text=text,
            method=method,
            page_count=page_count,
            warnings=warnings,
            filename=resolved_name,
        )
    if extension == ".docx":
        text, warnings = extract_docx(data)
        return ParsedDocument(
            text=text,
            method="docx",
            page_count=1,
            warnings=warnings,
            filename=resolved_name,
        )
    if extension == ".doc":
        raise UnsupportedResumeFormat(
            "Legacy .doc files are not supported. Export the resume as .docx or PDF."
        )
    raise UnsupportedResumeFormat("Upload a .pdf or .docx resume.")


def _resolve_filename(data: bytes, filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower()
    if extension:
        return filename
    if data.startswith(b"%PDF"):
        return "resume.pdf"
    if data.startswith(b"PK"):
        return "resume.docx"
    return filename or "resume"
