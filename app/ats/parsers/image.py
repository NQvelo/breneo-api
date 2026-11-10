"""Image resumes (JPG, PNG, WEBP, and similar) read with Tesseract."""

from __future__ import annotations

import io
import logging

from app.ats.config import get_setting
from app.ats.exceptions import CorruptResumeFile, EmptyResumeError, OCRUnavailable
from app.ats.parsers.georgian import clean_georgian_text
from app.ats.parsers.layout import words_to_text
from app.ats.textutil import meaningful_count

logger = logging.getLogger(__name__)


def extract_image(data: bytes) -> tuple[str, list[str]]:
    if not data:
        raise EmptyResumeError("The uploaded file is empty.")
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise OCRUnavailable("Image resumes need Pillow, which is not installed on the server.") from exc
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError as exc:
        raise OCRUnavailable("Image resumes need OCR, which is not installed on the server.") from exc

    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        image = image.convert("RGB")
    except Exception as exc:
        logger.exception("Resume image could not be opened")
        raise CorruptResumeFile("The image could not be opened. Upload a JPG, PNG, or WEBP resume.") from exc

    langs = str(get_setting("ATS_OCR_LANGS", "eng+kat") or "eng+kat")
    warnings = ["image_ocr"]
    try:
        text = _read(pytesseract, image, langs)
    except TesseractNotFoundError as exc:
        raise OCRUnavailable("Image resumes need OCR, which is not installed on the server.") from exc
    except Exception as exc:
        message = str(exc).lower()
        if "failed loading language" in message or "error opening data file" in message:
            warnings.append("ocr_lang_fallback_eng")
            text = _read(pytesseract, image, "eng")
        else:
            logger.exception("Image OCR failed")
            raise OCRUnavailable("OCR could not read this image.") from exc

    cleaned = clean_georgian_text(text)
    if meaningful_count(cleaned) < 20:
        raise EmptyResumeError("No resume text could be read from this image.")
    return cleaned, warnings


def _read(pytesseract, image, langs: str) -> str:
    raw = pytesseract.image_to_data(image, lang=langs, output_type=pytesseract.Output.DICT)
    words = []
    for index, value in enumerate(raw.get("text") or []):
        text = str(value or "").strip()
        if not text:
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
        words.append(
            {"text": text, "x0": left, "x1": left + width, "top": top, "bottom": top + height}
        )
    if words:
        ordered = words_to_text(words, float(image.width or 0))
        if meaningful_count(ordered) >= 20:
            return ordered
    return pytesseract.image_to_string(image, lang=langs) or ""
