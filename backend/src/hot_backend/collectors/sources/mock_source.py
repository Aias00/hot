from __future__ import annotations

from hot_backend.collectors.models import CollectRequest, DiscoveryCandidate, SourceConfig, SourceDocument
from hot_backend.collectors.sources.base import build_item


class MockHotSourceAdapter:
    adapter_kind = "mock-hot-source"

    async def discover(self, source: SourceConfig, request: CollectRequest, checkpoint: dict) -> list[DiscoveryCandidate]:
        seed_urls = source.seed_urls or [
            "https://example.com/mock/openai-research",
            "https://example.com/mock/ai-agents",
        ]
        return [
            DiscoveryCandidate(
                candidate_id=f"{source.source_id}-{index}",
                source_url=url,
                external_id=f"mock-{index}",
                metadata={"seed": True},
            )
            for index, url in enumerate(seed_urls[: request.limit], start=1)
        ]

    async def hydrate(self, source: SourceConfig, candidates: list[DiscoveryCandidate]) -> list[SourceDocument]:
        return [
            SourceDocument(
                candidate_id=candidate.candidate_id,
                source_url=candidate.source_url,
                title=f"Mock hot item from {source.title} #{index}",
                body="This is a placeholder hot-content document used to validate the collection graph.",
                author="mock-system",
                metadata={"external_id": candidate.external_id},
            )
            for index, candidate in enumerate(candidates, start=1)
        ]

    async def normalize(self, source: SourceConfig, documents: list[SourceDocument]):
        return [
            build_item(
                source=source,
                external_id=document.metadata.get("external_id") or document.candidate_id,
                canonical_url=document.source_url,
                title=document.title,
                summary=document.body or document.title,
                published_at=document.published_at,
                author=document.author,
                tags=["mock", "framework"],
            )
            for document in documents
        ]
