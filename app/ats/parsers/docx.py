"""DOCX ingestion. Legacy .doc (OLE) files are rejected by the reader."""

from __future__ import annotations

import io
import logging

from app.ats.exceptions import CorruptResumeFile, EmptyResumeError
from app.ats.parsers.georgian import clean_georgian_text
from app.ats.textutil import meaningful_count

logger = logging.getLogger(__name__)


def extract_docx(data: bytes) -> tuple[str, list[str]]:
    """Return cleaned document text and warnings."""
    if not data:
        raise EmptyResumeError("The uploaded file is empty.")
    try:
        from docx import Document
        from docx.opc.exceptions import PackageNotFoundError
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise CorruptResumeFile(
            "Word support is not installed on the server (python-docx)."
        ) from exc

    try:
        document = Document(io.BytesIO(data))
    except PackageNotFoundError as exc:
        raise CorruptResumeFile(
            "The Word file is corrupt or is not a .docx document."
        ) from exc
    except Exception as exc:
        logger.exception("DOCX open failed")
        raise CorruptResumeFile("The Word file could not be read.") from exc

    body_lines: list[str] = []
    try:
        for child in document.element.body.iterchildren():
            if child.tag == qn("w:p"):
                text = Paragraph(child, document).text.strip()
                if text:
                    body_lines.append(text)
            elif child.tag == qn("w:tbl"):
                body_lines.extend(_table_lines(Table(child, document)))
    except Exception as exc:
        logger.exception("DOCX body walk failed")
        raise CorruptResumeFile("The Word file could not be read.") from exc

    body = "\n".join(body_lines)
    header_bits = _header_footer_lines(document)
    links = [link for link in _hyperlinks(document) if link not in body]
    prefix = [line for line in header_bits if line and line not in body]
    combined = clean_georgian_text("\n".join([*prefix, body, *links]))
    if meaningful_count(combined) < 20:
        raise EmptyResumeError(
            "The Word file has no readable resume text. It may be empty or image-only."
        )
    warnings = []
    if prefix:
        warnings.append("header_included")
    if links:
        warnings.append("links_included")
    return combined, warnings


def _table_lines(table) -> list[str]:
    lines = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            value = " ".join(cell.text.split())
            if value and value not in cells:
                cells.append(value)
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _hyperlinks(document) -> list[str]:
    links = []
    try:
        rels = document.part.rels.values()
    except Exception:
        logger.warning("DOCX hyperlink read failed", exc_info=True)
        return []
    for rel in rels:
        if "hyperlink" not in str(getattr(rel, "reltype", "")):
            continue
        target = str(getattr(rel, "target_ref", "") or "").strip()
        if target and target not in links:
            links.append(target)
    return links


def _header_footer_lines(document) -> list[str]:
    lines: list[str] = []
    if not document.sections:
        return lines
    section = document.sections[0]
    for part in (section.header, section.footer):
        try:
            if part is None:
                continue
            for paragraph in part.paragraphs:
                text = paragraph.text.strip()
                if text:
                    lines.append(text)
        except Exception:
            logger.warning("Skipping a DOCX header or footer", exc_info=True)
    return lines
