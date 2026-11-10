"""Plain-text, HTML, and RTF resumes."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from app.ats.exceptions import EmptyResumeError
from app.ats.parsers.georgian import clean_georgian_text
from app.ats.textutil import meaningful_count


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")
        for key, value in attrs:
            if key in {"href", "src"} and value and not value.startswith(("#", "mailto:")):
                self.parts.append(f" {value} ")

    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data)


def extract_text_file(data: bytes) -> tuple[str, list[str]]:
    text = _decode(data)
    return _finish(text, [])


def extract_html(data: bytes) -> tuple[str, list[str]]:
    parser = _HTMLText()
    parser.feed(_decode(data))
    return _finish(" ".join(parser.parts), ["html"])


def extract_rtf(data: bytes) -> tuple[str, list[str]]:
    raw = _decode(data)
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", _rtf_hex, raw)
    raw = raw.replace("\\par", "\n").replace("\\line", "\n").replace("\\tab", " ")
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)
    raw = raw.replace("{", " ").replace("}", " ")
    return _finish(raw, ["rtf"])


def _rtf_hex(match: re.Match) -> str:
    try:
        return bytes.fromhex(match.group(0)[2:]).decode("latin-1")
    except ValueError:
        return ""


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _finish(text: str, warnings: list[str]) -> tuple[str, list[str]]:
    cleaned = clean_georgian_text(text or "")
    if meaningful_count(cleaned) < 20:
        raise EmptyResumeError("The file does not contain enough resume text.")
    return cleaned, warnings
