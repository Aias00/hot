from __future__ import annotations

from hashlib import sha256

from hot_backend.collectors.models import DiscoveryCandidate, NormalizedHotItem, SourceConfig, SourceDocument
from hot_backend.text_clean import clean_text_fragment


def build_content_hash(title: str, summary: str, canonical_url: str) -> str:
    return sha256(f"{title}\n{summary}\n{canonical_url}".encode("utf-8")).hexdigest()


def build_item(
    *,
    source: SourceConfig,
    external_id: str,
    canonical_url: str,
    title: str,
    summary: str,
    published_at=None,
    author: str | None = None,
    tags: list[str] | None = None,
) -> NormalizedHotItem:
    normalized_title = clean_text_fragment(title)
    normalized_summary = clean_text_fragment(summary)
    return NormalizedHotItem(
        source_id=source.source_id,
        external_id=external_id,
        canonical_url=canonical_url,
        title=normalized_title,
        summary=normalized_summary,
        published_at=published_at,
        author=author,
        tags=tags or [],
        content_hash=build_content_hash(normalized_title, normalized_summary, canonical_url),
    )


__all__ = [
    "DiscoveryCandidate",
    "NormalizedHotItem",
    "SourceConfig",
    "SourceDocument",
    "build_content_hash",
    "build_item",
]
