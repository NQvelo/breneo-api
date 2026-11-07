"""PDF ingestion: digital text via pdfplumber, scanned pages via Tesseract."""

from __future__ import annotations

import io
import logging

from app.ats.config import get_int_setting, get_setting
from app.ats.exceptions import (
    CorruptResumeFile,
    EmptyResumeError,
    OCRUnavailable,
    PasswordProtectedPDF,
)
from app.ats.parsers.georgian import clean_georgian_text
from app.ats.parsers.layout import words_to_text
from app.ats.textutil import meaningful_count

logger = logging.getLogger(__name__)


def _is_password_error(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "password" in name or "password" in message or "encrypted" in message


def _is_missing_language(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "failed loading language" in message or "error opening data file" in message


def extract_pdf(data: bytes) -> tuple[str, str, int, list[str]]:
    """Return cleaned text, method (``digital`` or ``ocr``), page count, and warnings."""
    if not data:
        raise EmptyResumeError("The uploaded file is empty.")
    if not data.startswith(b"%PDF"):
        raise CorruptResumeFile("The file is not a valid PDF.")

    try:
        import pdfplumber
    except ImportError as exc:
        raise CorruptResumeFile(
            "PDF support is not installed on the server (pdfplumber)."
        ) from exc

    warnings: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                raise EmptyResumeError("The PDF has no pages.")
            chunks: list[str] = []
            max_pages = get_int_setting("ATS_MAX_PAGES", 8)
            for index, page in enumerate(pdf.pages[:max_pages]):
                chunks.append(_read_page(page, index, warnings))
            if page_count > max_pages:
                warnings.append("truncated_pages")
    except (PasswordProtectedPDF, EmptyResumeError, CorruptResumeFile):
        raise
    except Exception as exc:
        if _is_password_error(exc):
            raise PasswordProtectedPDF(
                "This PDF is password-protected. Upload an unlocked copy."
            ) from exc
        logger.exception("PDF digital extraction failed")
        raise CorruptResumeFile(
            "The PDF could not be read. It may be corrupt or incomplete."
        ) from exc

    digital_text = clean_georgian_text("\n\n".join(chunk for chunk in chunks if chunk.strip()))
    if _text_is_sufficient(digital_text, min(page_count, get_int_setting("ATS_MAX_PAGES", 8))):
        return digital_text, "digital", page_count, warnings

    try:
        ocr_text, ocr_warnings = _ocr_pdf(data)
    except OCRUnavailable:
        if digital_text.strip():
            warnings.append("ocr_unavailable")
            return digital_text, "digital", page_count, warnings
        raise
    except (PasswordProtectedPDF, CorruptResumeFile, EmptyResumeError):
        raise
    except Exception as exc:
        logger.exception("PDF OCR failed")
        if digital_text.strip():
            warnings.append("ocr_failed")
            return digital_text, "digital", page_count, warnings
        raise CorruptResumeFile(
            "The scanned PDF could not be processed."
        ) from exc

    warnings.extend(ocr_warnings)
    ocr_clean = clean_georgian_text(ocr_text)
    if meaningful_count(ocr_clean) >= meaningful_count(digital_text) and ocr_clean.strip():
        return ocr_clean, "ocr", page_count, warnings
    if digital_text.strip():
        return digital_text, "digital", page_count, warnings
    raise EmptyResumeError(
        "No text could be read from this PDF. If it is a scan, check that the pages are not blank."
    )


def _read_page(page, index: int, warnings: list[str]) -> str:
    try:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False) or []
        width = float(page.width or 0)
        if words:
            return words_to_text(words, width)
        return page.extract_text() or ""
    except Exception:
        logger.warning("Skipping unreadable PDF page %s", index + 1, exc_info=True)
        warnings.append(f"unreadable_page_{index + 1}")
        return ""


def _text_is_sufficient(text: str, page_count: int) -> bool:
    count = meaningful_count(text)
    if count < 80:
        return False
    return count / max(page_count, 1) >= 40


def _ocr_pdf(data: bytes) -> tuple[str, list[str]]:
    try:
        from pdf2image import convert_from_bytes
        from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError
    except ImportError as exc:
        raise OCRUnavailable(
            "This PDF has no text layer, and scanned-PDF support is not installed on the server."
        ) from exc

    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError as exc:
        raise OCRUnavailable(
            "This PDF has no text layer, and OCR is not installed on the server."
        ) from exc

    dpi = get_int_setting("ATS_OCR_DPI", 200)
    max_pages = get_int_setting("ATS_MAX_PAGES", 8)
    langs = str(get_setting("ATS_OCR_LANGS", "eng+kat") or "eng+kat")
    warnings: list[str] = []
    try:
        images = convert_from_bytes(
            data,
            dpi=dpi,
            first_page=1,
            last_page=max_pages,
            fmt="png",
        )
    except PDFInfoNotInstalledError as exc:
        raise OCRUnavailable(
            "This PDF has no text layer, and scanned-PDF support is not installed on the server."
        ) from exc
    except PDFPageCountError as exc:
        raise CorruptResumeFile("The PDF page count could not be read.") from exc
    except Exception as exc:
        if _is_password_error(exc):
            raise PasswordProtectedPDF(
                "This PDF is password-protected. Upload an unlocked copy."
            ) from exc
        logger.exception("pdf2image failed")
        raise CorruptResumeFile("The scanned PDF could not be rendered.") from exc

    if not images:
        raise EmptyResumeError("The PDF has no pages to recognize.")

    active_langs = langs
    pages: list[str] = []
    for image in images:
        try:
            text, active_langs, fell_back = _ocr_image(pytesseract, image, active_langs)
        except TesseractNotFoundError as exc:
            raise OCRUnavailable(
                "This PDF has no text layer, and OCR is not installed on the server."
            ) from exc
        except Exception as exc:
            logger.exception("Tesseract failed on a resume page")
            raise OCRUnavailable(
                "This PDF has no text layer, and OCR could not read it."
            ) from exc
        if fell_back:
            warnings.append("ocr_lang_fallback_eng")
        pages.append(text)
    if len(images) == max_pages:
        warnings.append("truncated_pages")
    return "\n\n".join(pages), list(dict.fromkeys(warnings))


def _ocr_image(pytesseract, image, langs: str) -> tuple[str, str, bool]:
    try:
        return _ocr_image_once(pytesseract, image, langs), langs, False
    except Exception as exc:
        if langs != "eng" and _is_missing_language(exc):
            logger.warning("Tesseract language pack %s is missing; falling back to eng", langs)
            return _ocr_image_once(pytesseract, image, "eng"), "eng", True
        raise


def _ocr_image_once(pytesseract, image, langs: str) -> str:
    try:
        raw = pytesseract.image_to_data(image, lang=langs, output_type=pytesseract.Output.DICT)
        words = _words_from_tesseract(raw)
        if words:
            width = float(getattr(image, "width", 0) or max(word["x1"] for word in words))
            text = words_to_text(words, width)
            if meaningful_count(text) >= 20:
                return text
    except Exception:
        logger.warning("Tesseract layout pass failed; using plain OCR text", exc_info=True)
    return pytesseract.image_to_string(image, lang=langs) or ""


def _words_from_tesseract(raw: dict) -> list[dict]:
    words = []
    texts = raw.get("text") or []
    for index, text in enumerate(texts):
        value = str(text or "").strip()
        if not value:
            continue
        try:
            confidence = float(raw["conf"][index])
        except (KeyError, TypeError, ValueError):
            confidence = -1
        if confidence < 0:
            continue
        left = float(raw["left"][index])
        top = float(raw["top"][index])
        width = float(raw["width"][index])
        height = float(raw["height"][index])
        words.append(
            {
                "text": value,
                "x0": left,
                "x1": left + width,
                "top": top,
                "bottom": top + height,
            }
        )
    return words
