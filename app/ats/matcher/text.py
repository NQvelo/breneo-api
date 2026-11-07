"""Token helpers for bilingual keyword overlap."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9+#.\u10a0-\u10ff]{2,}", re.IGNORECASE)

_STOPWORDS = frozenset(
    {
        "ა",
        "an",
        "and",
        "არ",
        "არის",
        "as",
        "at",
        "be",
        "by",
        "და",
        "ეს",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "our",
        "რომ",
        "the",
        "this",
        "to",
        "with",
        "you",
        "your",
        "ან",
        "თუ",
        "იყო",
        "მას",
        "მისი",
        "ჩვენ",
        "ყველა",
        "ასევე",
        "a",
    }
)

_ALIASES = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "k8s": "kubernetes",
    "reactjs": "react",
    "react.js": "react",
    "node": "nodejs",
    "nodejs": "nodejs",
    "node.js": "nodejs",
    "py": "python",
    "python": "python",
    "golang": "go",
}


def normalize_token(token: str) -> str:
    text = (token or "").strip().casefold()
    text = text.strip(".,;:|/\\()[]{}\"'")
    return _ALIASES.get(text, text)


def tokenize(text: str) -> list[str]:
    tokens = []
    for match in _TOKEN_RE.findall(text or ""):
        token = normalize_token(match)
        if len(token) < 2 or token in _STOPWORDS or token.isdigit():
            continue
        tokens.append(token)
    return tokens


def token_set(text: str) -> set[str]:
    return set(tokenize(text))
