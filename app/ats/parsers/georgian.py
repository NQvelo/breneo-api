"""Georgian Unicode cleanup for resumes extracted from PDFs and Word files.

Handles four real-world glitches:

* UTF-8 Mkhedruli misread as cp1252 (the ``áƒ`` mojibake pattern)
* Mtavruli capitals folded to Mkhedruli so matching is stable
* Invisible characters, ligatures, and private-use glyphs from embedded fonts
* Legacy AcadNusx-style fonts that store Mkhedruli in Latin code points
  (``saqarTvelo`` -> ``საქართველო``). Conversion runs only on tokens that look
  like that encoding, so ordinary English prose is left alone.
"""

from __future__ import annotations

import re
import unicodedata

from app.ats.textutil import georgian_count

# AcadNusx / BPG single-letter font encoding -> Mkhedruli.
_ASCII_MAP = {
    "a": "ა",
    "b": "ბ",
    "c": "ც",
    "d": "დ",
    "e": "ე",
    "f": "ფ",
    "g": "გ",
    "h": "ჰ",
    "i": "ი",
    "j": "ჯ",
    "k": "კ",
    "l": "ლ",
    "m": "მ",
    "n": "ნ",
    "o": "ო",
    "p": "პ",
    "q": "ქ",
    "r": "რ",
    "s": "ს",
    "t": "ტ",
    "u": "უ",
    "v": "ვ",
    "w": "წ",
    "x": "ხ",
    "y": "ყ",
    "z": "ზ",
    "C": "ჩ",
    "J": "ჟ",
    "R": "ღ",
    "S": "შ",
    "T": "თ",
    "W": "ჭ",
    "Z": "ძ",
}

_LIGATURES = {
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬀ": "ff",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
}

_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad\u2060"))

_EN_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
        "you",
        "your",
        "experience",
        "education",
        "skills",
        "summary",
        "work",
        "university",
        "project",
        "manager",
        "engineer",
        "developer",
        "software",
        "years",
        "year",
    }
)

_TECH = frozenset(
    {
        "api",
        "aws",
        "azure",
        "css",
        "django",
        "docker",
        "excel",
        "fastapi",
        "figma",
        "flask",
        "git",
        "github",
        "gitlab",
        "graphql",
        "html",
        "http",
        "https",
        "java",
        "javascript",
        "jira",
        "json",
        "jwt",
        "kotlin",
        "kubernetes",
        "linux",
        "mongodb",
        "mysql",
        "nginx",
        "node",
        "nodejs",
        "numpy",
        "oauth",
        "pandas",
        "php",
        "postgres",
        "postgresql",
        "python",
        "react",
        "redis",
        "rest",
        "ruby",
        "rust",
        "scrum",
        "sql",
        "sqlite",
        "typescript",
        "vue",
        "xml",
        "yaml",
    }
)

_DO_NOT_CONVERT = _EN_STOP | _TECH | {"iraq", "qatar", "qantas", "compaq"}

_TOKEN_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|https?://\S+"
    r"|[A-Za-z]+"
    r"|[^A-Za-z]+"
)
_MID_CAP_RE = re.compile(r"[a-z][CJRSWTZ]")
_Q_NOT_U_RE = re.compile(r"q(?!u)", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"\d{1,3}")


def clean_georgian_text(text: str) -> str:
    """Normalize resume text so English and Mkhedruli can be matched reliably."""
    if not text:
        return ""
    cleaned = text.replace("\x00", "")
    cleaned = _repair_mojibake(cleaned)
    cleaned = unicodedata.normalize("NFC", cleaned)
    cleaned = cleaned.translate(_INVISIBLE)
    for source, target in _LIGATURES.items():
        cleaned = cleaned.replace(source, target)
    cleaned = cleaned.replace("\u00a0", " ").replace("\u10fb", "\n")
    cleaned = _fold_mtavruli(cleaned)
    cleaned = _strip_controls(cleaned)
    cleaned = _convert_ascii_georgian(cleaned)
    cleaned = _tidy_whitespace(cleaned)
    return cleaned.strip()


def _looks_like_mojibake(text: str) -> bool:
    # cp1252 reads the UTF-8 lead bytes E1 83 as "áƒ"; latin-1 reads them as "á" + U+0083.
    return "áƒ" in text or "á\u0083" in text


def _mojibake_bytes(line: str) -> bytes | None:
    """Map a mis-decoded line back to the original UTF-8 bytes.

    Python's cp1252 codec leaves a few bytes undefined (including 0x90, which
    is the trailing byte of ``ა``), so those characters are kept as Latin-1.
    """
    raw = bytearray()
    for char in line:
        try:
            encoded = char.encode("cp1252")
        except UnicodeEncodeError:
            encoded = b""
        if len(encoded) == 1:
            raw.extend(encoded)
            continue
        code = ord(char)
        if code <= 0xFF:
            raw.append(code)
            continue
        return None
    return bytes(raw)


def _repair_mojibake(text: str) -> str:
    if not _looks_like_mojibake(text):
        return text
    repaired_lines = []
    changed = False
    for line in text.splitlines():
        if not _looks_like_mojibake(line):
            repaired_lines.append(line)
            continue
        raw = _mojibake_bytes(line)
        if raw is None:
            repaired_lines.append(line)
            continue
        try:
            fixed = raw.decode("utf-8")
        except UnicodeDecodeError:
            repaired_lines.append(line)
            continue
        if georgian_count(fixed) > georgian_count(line):
            repaired_lines.append(fixed)
            changed = True
        else:
            repaired_lines.append(line)
    if not changed:
        return text
    return "\n".join(repaired_lines)


def _fold_mtavruli(text: str) -> str:
    chars = []
    for char in text:
        code = ord(char)
        if 0x1C90 <= code <= 0x1CBF:
            chars.append(chr(code - 0xBC0))
        else:
            chars.append(char)
    return "".join(chars)


def _strip_controls(text: str) -> str:
    kept = []
    for char in text:
        code = ord(char)
        if char in "\n\t\r":
            kept.append(char)
            continue
        if code < 32 or code == 0x7F:
            continue
        if 0xE000 <= code <= 0xF8FF:
            continue
        kept.append(char)
    return "".join(kept)


def _token_signal(token: str) -> bool:
    if len(token) < 3 or not token.isalpha() or not token.isascii():
        return False
    if token.lower() in _DO_NOT_CONVERT:
        return False
    if _MID_CAP_RE.search(token):
        return True
    if _Q_NOT_U_RE.search(token):
        return True
    return False


def _should_convert_token(token: str) -> bool:
    if not token.isalpha() or not token.isascii() or len(token) < 3:
        return False
    if token.lower() in _DO_NOT_CONVERT:
        return False
    if token.isupper() and len(token) <= 4:
        return False
    return all(char in _ASCII_MAP for char in token)


def _convert_token(token: str) -> str:
    return "".join(_ASCII_MAP.get(char, char) for char in token)


def _convert_line(line: str, force_all: bool) -> str:
    parts = _TOKEN_RE.findall(line)
    words = [part for part in parts if part.isalpha()]
    strong = [word for word in words if _token_signal(word)]
    has_stopword = any(word.lower() in _EN_STOP for word in words)
    convert_rest = force_all or (bool(strong) and not has_stopword)
    converted = []
    for part in parts:
        if not part.isalpha():
            converted.append(part)
            continue
        if part in strong or (convert_rest and _should_convert_token(part)):
            converted.append(_convert_token(part))
        else:
            converted.append(part)
    return "".join(converted)


def _document_is_ascii_georgian(text: str) -> bool:
    if georgian_count(text) > 10:
        return False
    words = re.findall(r"[A-Za-z]{2,}", text)
    if len(words) < 8:
        return False
    stop_hits = sum(1 for word in words if word.lower() in _EN_STOP or word.lower() in _TECH)
    if stop_hits / len(words) >= 0.08:
        return False
    signals = sum(1 for word in words if _token_signal(word))
    if signals >= 2:
        return True
    return signals >= 1 and stop_hits == 0 and len(words) >= 12


def _convert_ascii_georgian(text: str) -> str:
    force_all = _document_is_ascii_georgian(text)
    return "\n".join(_convert_line(line, force_all) for line in text.splitlines())


def _tidy_whitespace(text: str) -> str:
    lines = []
    blank_run = 0
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if _PAGE_NUMBER_RE.fullmatch(line):
            continue
        if not line:
            blank_run += 1
            if blank_run <= 2:
                lines.append("")
            continue
        blank_run = 0
        lines.append(line)
    return "\n".join(lines).strip()
