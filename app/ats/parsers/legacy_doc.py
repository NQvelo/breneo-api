"""Best-effort text recovery for legacy Word .doc files."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile

from app.ats.exceptions import UnsupportedResumeFormat
from app.ats.parsers.georgian import clean_georgian_text
from app.ats.parsers.plain import _finish

logger = logging.getLogger(__name__)


def extract_doc(data: bytes) -> tuple[str, list[str]]:
    text = _antiword(data) or _printable_runs(data)
    try:
        cleaned, warnings = _finish(text, ["legacy_doc"])
    except Exception as exc:
        raise UnsupportedResumeFormat(
            "This .doc file could not be read. Export it as .docx or PDF and upload that."
        ) from exc
    return cleaned, warnings


def _antiword(data: bytes) -> str:
    binary = shutil.which("antiword")
    if not binary:
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".doc") as handle:
            handle.write(data)
            handle.flush()
            result = subprocess.run(
                [binary, handle.name],
                check=False,
                capture_output=True,
                timeout=20,
            )
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("antiword failed on a .doc resume", exc_info=True)
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="ignore")


def _printable_runs(data: bytes) -> str:
    parts: list[str] = []
    utf16 = data.decode("utf-16le", errors="ignore")
    parts.append(_keep_words(utf16))
    current: list[str] = []
    for byte in data:
        if 32 <= byte < 127 or byte in (9, 10, 13):
            current.append(chr(byte))
            continue
        if len(current) >= 6:
            parts.append("".join(current))
        current = []
    if len(current) >= 6:
        parts.append("".join(current))
    return clean_georgian_text("\n".join(part for part in parts if part.strip()))


def _keep_words(text: str) -> str:
    words = []
    current: list[str] = []
    for char in text:
        if char.isprintable() or char in "\n\t":
            current.append(char)
            continue
        if len(current) >= 4:
            words.append("".join(current))
        current = []
    if len(current) >= 4:
        words.append("".join(current))
    return "\n".join(words)
