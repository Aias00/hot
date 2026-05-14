from __future__ import annotations

import re
from html import unescape


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_BOILERPLATE_PATTERNS = [
    re.compile(
        r"(?:^|\s)The post .*? appeared first on .*?(?:[.!?](?=\s|$)|$)",
        re.IGNORECASE,
    ),
]


def clean_text_fragment(value: str | None) -> str:
    if not value:
        return ""

    normalized = unescape(value)
    normalized = _TAG_RE.sub(" ", normalized)
    for pattern in _BOILERPLATE_PATTERNS:
        normalized = pattern.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    normalized = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", normalized)
    return normalized
