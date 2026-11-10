"""Dispatch resume bytes to the parser that matches the file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.ats.exceptions import EmptyResumeError, UnsupportedResumeFormat
from app.ats.parsers.docx import extract_docx
from app.ats.parsers.image import extract_image
from app.ats.parsers.legacy_doc import extract_doc
from app.ats.parsers.pdf import extract_pdf
from app.ats.parsers.plain import extract_html, extract_rtf, extract_text_file

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"}


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
        return ParsedDocument(text, method, page_count, warnings, resolved_name)
    if extension == ".docx":
        text, warnings = extract_docx(data)
        return ParsedDocument(text, "docx", 1, warnings, resolved_name)
    if extension == ".doc":
        text, warnings = extract_doc(data)
        return ParsedDocument(text, "doc", 1, warnings, resolved_name)
    if extension in {".txt", ".text"}:
        text, warnings = extract_text_file(data)
        return ParsedDocument(text, "txt", 1, warnings, resolved_name)
    if extension in {".html", ".htm"}:
        text, warnings = extract_html(data)
        return ParsedDocument(text, "html", 1, warnings, resolved_name)
    if extension == ".rtf":
        text, warnings = extract_rtf(data)
        return ParsedDocument(text, "rtf", 1, warnings, resolved_name)
    if extension in _IMAGE_EXTENSIONS:
        text, warnings = extract_image(data)
        return ParsedDocument(text, "image", 1, warnings, resolved_name)
    raise UnsupportedResumeFormat(
        "Upload a PDF, Word, text, HTML, RTF, or image resume (JPG, PNG, or WEBP)."
    )


def _resolve_filename(data: bytes, filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower()
    detected = _detect_extension(data)
    if extension:
        return filename
    if detected:
        return f"resume{detected}"
    return filename or "resume"


def _detect_extension(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return ".pdf"
    if data.startswith(b"PK"):
        return ".docx"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return ".doc"
    if data.startswith(b"{\\rtf"):
        return ".rtf"
    stripped = data.lstrip()[:32].lower()
    if stripped.startswith((b"<!doctype html", b"<html")):
        return ".html"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"GIF8"):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return ""
