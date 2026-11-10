"""Read a resume into positioned blocks. The file is not flattened before layout."""

from __future__ import annotations

import io
import logging
import os

from app.ats.config import get_int_setting, get_setting
from app.ats.exceptions import (
    CorruptResumeFile,
    EmptyResumeError,
    OCRUnavailable,
    PasswordProtectedPDF,
    UnsupportedResumeFormat,
)
from app.ats.parsers.georgian import clean_georgian_text
from app.ats.pipeline.layout import order_blocks
from app.ats.pipeline.model import Block, ResumeDocument
from app.ats.textutil import meaningful_count

logger = logging.getLogger(__name__)

_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"}


def load_document(data: bytes, filename: str) -> ResumeDocument:
    if not data:
        raise EmptyResumeError("The uploaded file is empty.")
    name = _name_for(data, filename or "")
    extension = os.path.splitext(name)[1].lower()
    if extension == ".pdf":
        document = _read_pdf(data)
    elif extension == ".docx":
        document = _read_docx(data)
    elif extension == ".doc":
        document = _read_doc(data)
    elif extension in {".txt", ".text"}:
        document = _read_plain(data, "txt")
    elif extension in {".html", ".htm"}:
        document = _read_html(data)
    elif extension == ".rtf":
        document = _read_rtf(data)
    elif extension in _IMAGES:
        document = _read_image(data)
    else:
        raise UnsupportedResumeFormat(
            "Upload a PDF, Word, text, HTML, RTF, or image resume (JPG, PNG, or WEBP)."
        )
    document.filename = name
    document.blocks = [block for block in document.blocks if block.text]
    if meaningful_count(document.ordered_text()) < 20:
        raise EmptyResumeError(
            "The file was read, but it does not contain enough resume text."
        )
    return document


def document_from_text(text: str, filename: str = "") -> ResumeDocument:
    blocks = []
    for index, line in enumerate((text or "").splitlines()):
        cleaned = clean_georgian_text(line).strip()
        if cleaned:
            blocks.append(Block(text=cleaned, y0=float(index), y1=float(index + 1), x1=100))
    return ResumeDocument(blocks=blocks, method="text", kind="text", filename=filename)


def _read_pdf(data: bytes) -> ResumeDocument:
    if not data.startswith(b"%PDF"):
        raise CorruptResumeFile("The file is not a valid PDF.")
    try:
        import pdfplumber
    except ImportError as exc:
        raise CorruptResumeFile("PDF support is not installed on the server (pdfplumber).") from exc

    warnings: list[str] = []
    blocks: list[Block] = []
    sparse_pages: list[int] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                raise EmptyResumeError("The PDF has no pages.")
            max_pages = get_int_setting("ATS_MAX_PAGES", 8)
            for index, page in enumerate(pdf.pages[:max_pages]):
                page_blocks = _pdf_page(page, index + 1)
                blocks.extend(page_blocks)
                if len(page_blocks) < 6 and getattr(page, "images", None):
                    sparse_pages.append(index + 1)
            if page_count > max_pages:
                warnings.append("truncated_pages")
    except (PasswordProtectedPDF, EmptyResumeError, CorruptResumeFile):
        raise
    except Exception as exc:
        if "password" in str(exc).lower() or "encrypt" in str(exc).lower():
            raise PasswordProtectedPDF(
                "This PDF is password-protected. Upload an unlocked copy."
            ) from exc
        logger.exception("PDF layout extraction failed")
        raise CorruptResumeFile("The PDF could not be read. It may be corrupt or incomplete.") from exc

    kind = "digital"
    if sparse_pages or meaningful_count("\n".join(block.text for block in blocks)) < 80:
        ocr_blocks, ocr_warnings = _safe_ocr(data)
        warnings.extend(ocr_warnings)
        if meaningful_count("\n".join(block.text for block in ocr_blocks)) > meaningful_count(
            "\n".join(block.text for block in blocks)
        ):
            blocks = ocr_blocks
            kind = "hybrid" if blocks else "scanned"
            warnings.append("ocr_used")
    if not blocks:
        raise EmptyResumeError("No text could be read from this PDF.")
    return ResumeDocument(blocks=blocks, page_count=page_count, method="pdf", kind=kind, warnings=warnings)


def _pdf_page(page, page_number: int) -> list[Block]:
    width = float(page.width or 0)
    table_boxes = []
    blocks: list[Block] = []
    try:
        tables = page.find_tables() or []
    except Exception:
        tables = []
    for table in tables:
        box = getattr(table, "bbox", None)
        if box:
            table_boxes.append(box)
        rows = table.extract() or []
        blocks.extend(_table_blocks(rows, page_number, box))
    try:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False) or []
    except Exception:
        logger.warning("PDF word extraction failed on page %s", page_number, exc_info=True)
        words = []
    words = [word for word in words if not _inside_tables(word, table_boxes)]
    blocks.extend(_lines_from_words(words, page_number))
    try:
        for item in page.hyperlinks or []:
            uri = str((item or {}).get("uri") or "").strip()
            if uri:
                blocks.append(Block(text=uri, page=page_number, y0=float(page.height or 0), x1=width))
    except Exception:
        logger.warning("PDF hyperlink read failed", exc_info=True)
    return order_blocks(blocks, width)


def _lines_from_words(words: list[dict], page_number: int) -> list[Block]:
    lines: list[dict] = []
    for word in sorted(words, key=lambda item: (float(item.get("top") or 0), float(item.get("x0") or 0))):
        text = clean_georgian_text(str(word.get("text") or "")).strip()
        if not text:
            continue
        top = float(word.get("top") or 0)
        height = max(1.0, float(word.get("bottom") or top) - top)
        placed = False
        for line in lines:
            if abs(top - line["top"]) <= max(2.0, height * 0.6):
                line["words"].append((float(word.get("x0") or 0), float(word.get("x1") or 0), top, float(word.get("bottom") or top), text))
                line["top"] = min(line["top"], top)
                placed = True
                break
        if not placed:
            lines.append(
                {
                    "top": top,
                    "words": [(float(word.get("x0") or 0), float(word.get("x1") or 0), top, float(word.get("bottom") or top), text)],
                }
            )
    blocks = []
    for line in lines:
        words_sorted = sorted(line["words"], key=lambda item: item[0])
        blocks.append(
            Block(
                text=" ".join(item[4] for item in words_sorted),
                page=page_number,
                x0=min(item[0] for item in words_sorted),
                x1=max(item[1] for item in words_sorted),
                y0=min(item[2] for item in words_sorted),
                y1=max(item[3] for item in words_sorted),
            )
        )
    return blocks


def _table_blocks(rows: list[list], page_number: int, box) -> list[Block]:
    cleaned = [[clean_georgian_text(str(cell or "")).strip() for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(row)]
    if not cleaned:
        return []
    date_rows = sum(1 for row in cleaned if any(_looks_like_date(cell) for cell in row))
    column_major = len(cleaned[0]) >= 2 and date_rows < 2
    blocks: list[Block] = []
    x_base = float(box[0]) if box else 0.0
    y_base = float(box[1]) if box else 0.0
    if column_major:
        width = max(len(row) for row in cleaned)
        for column in range(width):
            for row_index, row in enumerate(cleaned):
                if column < len(row) and row[column]:
                    blocks.append(
                        Block(
                            text=row[column],
                            page=page_number,
                            x0=x_base + column * 200,
                            x1=x_base + (column + 1) * 200,
                            y0=y_base + row_index,
                            y1=y_base + row_index + 1,
                            column=column,
                            region=0,
                        )
                    )
        return blocks
    for row_index, row in enumerate(cleaned):
        for column, cell in enumerate(row):
            if cell:
                blocks.append(
                    Block(
                        text=cell,
                        page=page_number,
                        x0=x_base + column,
                        x1=x_base + column + 1,
                        y0=y_base + row_index,
                        y1=y_base + row_index + 1,
                        column=0,
                        region=0,
                    )
                )
    return blocks


def _inside_tables(word: dict, boxes: list) -> bool:
    if not boxes:
        return False
    x = (float(word.get("x0") or 0) + float(word.get("x1") or 0)) / 2
    y = (float(word.get("top") or 0) + float(word.get("bottom") or 0)) / 2
    for x0, y0, x1, y1 in boxes:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


def _looks_like_date(text: str) -> bool:
    import re

    return bool(re.search(r"(19|20)\d{2}|present|დღემდე", text or "", re.I))


def _safe_ocr(data: bytes) -> tuple[list[Block], list[str]]:
    try:
        return _ocr_pdf(data)
    except (OCRUnavailable, CorruptResumeFile, PasswordProtectedPDF, EmptyResumeError):
        return [], ["ocr_unavailable"]
    except Exception:
        logger.exception("OCR layout pass failed")
        return [], ["ocr_failed"]


def _ocr_pdf(data: bytes) -> tuple[list[Block], list[str]]:
    from pdf2image import convert_from_bytes

    import pytesseract

    max_pages = get_int_setting("ATS_MAX_PAGES", 8)
    dpi = get_int_setting("ATS_OCR_DPI", 200)
    langs = str(get_setting("ATS_OCR_LANGS", "eng+kat") or "eng+kat")
    images = convert_from_bytes(data, dpi=dpi, first_page=1, last_page=max_pages, fmt="png")
    blocks: list[Block] = []
    warnings: list[str] = []
    for page_number, image in enumerate(images, start=1):
        try:
            raw = pytesseract.image_to_data(image, lang=langs, output_type=pytesseract.Output.DICT)
        except Exception as exc:
            if "failed loading language" in str(exc).lower():
                warnings.append("ocr_lang_fallback_eng")
                raw = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)
            else:
                raise
        words = []
        for index, text in enumerate(raw.get("text") or []):
            value = clean_georgian_text(str(text or "")).strip()
            if not value:
                continue
            try:
                confidence = float(raw["conf"][index])
            except (KeyError, TypeError, ValueError, IndexError):
                confidence = -1
            if confidence < 0:
                continue
            left = float(raw["left"][index])
            top = float(raw["top"][index])
            width = float(raw["width"][index])
            height = float(raw["height"][index])
            words.append({"text": value, "x0": left, "x1": left + width, "top": top, "bottom": top + height})
        page_blocks = order_blocks(_lines_from_words(words, page_number), float(getattr(image, "width", 0) or 0))
        blocks.extend(page_blocks)
    return blocks, warnings


def _read_docx(data: bytes) -> ResumeDocument:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise CorruptResumeFile("The Word file could not be read.") from exc
    blocks: list[Block] = []
    row = 0
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = clean_georgian_text(Paragraph(child, document).text).strip()
            if text:
                blocks.append(Block(text=text, y0=float(row), y1=float(row + 1), x1=100))
                row += 1
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            rows = [[clean_georgian_text(cell.text).strip() for cell in table_row.cells] for table_row in table.rows]
            table_blocks = _table_blocks(rows, 1, None)
            for block in table_blocks:
                block.y0 += row
                block.y1 += row
            blocks.extend(order_blocks(table_blocks, 600))
            row += len(rows) + 1
    return ResumeDocument(blocks=blocks, method="docx", kind="docx")


def _read_doc(data: bytes) -> ResumeDocument:
    from app.ats.parsers.legacy_doc import extract_doc

    text, warnings = extract_doc(data)
    document = document_from_text(text, "")
    document.method = "doc"
    document.kind = "doc"
    document.warnings = warnings
    return document


def _read_plain(data: bytes, method: str) -> ResumeDocument:
    from app.ats.parsers.plain import extract_text_file

    text, warnings = extract_text_file(data)
    document = document_from_text(text, "")
    document.method = method
    document.warnings = warnings
    return document


def _read_html(data: bytes) -> ResumeDocument:
    from app.ats.parsers.plain import extract_html

    text, warnings = extract_html(data)
    document = document_from_text(text, "")
    document.method = "html"
    document.warnings = warnings
    return document


def _read_rtf(data: bytes) -> ResumeDocument:
    from app.ats.parsers.plain import extract_rtf

    text, warnings = extract_rtf(data)
    document = document_from_text(text, "")
    document.method = "rtf"
    document.warnings = warnings
    return document


def _read_image(data: bytes) -> ResumeDocument:
    from app.ats.parsers.image import extract_image

    text, warnings = extract_image(data)
    document = document_from_text(text, "")
    document.method = "image"
    document.kind = "scanned"
    document.warnings = warnings
    return document


def _name_for(data: bytes, filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower()
    if extension:
        return filename
    if data.startswith(b"%PDF"):
        return "resume.pdf"
    if data.startswith(b"PK"):
        return "resume.docx"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "resume.doc"
    if data.startswith(b"{\\rtf"):
        return "resume.rtf"
    if data.lstrip()[:32].lower().startswith((b"<!doctype html", b"<html")):
        return "resume.html"
    if data.startswith(b"\xff\xd8\xff"):
        return "resume.jpg"
    if data.startswith(b"\x89PNG"):
        return "resume.png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "resume.webp"
    return filename or "resume"
