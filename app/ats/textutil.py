"""Script detection shared by the parser, extractor, and matcher."""

from __future__ import annotations

import re

_GEORGIAN_RE = re.compile(r"[\u10A0-\u10FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def georgian_count(text: str) -> int:
    return len(_GEORGIAN_RE.findall(text or ""))


def latin_count(text: str) -> int:
    return len(_LATIN_RE.findall(text or ""))


def detect_language(text: str) -> str:
    """Return ``en``, ``ka``, ``mixed``, or ``unknown`` from letter counts."""
    geo = georgian_count(text)
    lat = latin_count(text)
    if geo == 0 and lat == 0:
        return "unknown"
    if geo == 0:
        return "en"
    if lat == 0:
        return "ka"
    total = geo + lat
    if geo / total >= 0.75:
        return "ka"
    if lat / total >= 0.75:
        return "en"
    return "mixed"


def meaningful_count(text: str) -> int:
    return len(re.findall(r"[0-9A-Za-z\u10A0-\u10FF]", text or ""))
