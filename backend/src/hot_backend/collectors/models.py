from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class CollectorRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceConfig(BaseModel):
    source_id: str
    adapter_kind: str
    title: str
    description: str
    enabled: bool = True
    base_url: str | None = None
    seed_urls: list[str] = Field(default_factory=list)
    config_json: dict[str, Any] = Field(default_factory=dict)


class DiscoveryCandidate(BaseModel):
    candidate_id: str
    source_url: str
    external_id: str | None = None
    discovered_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceDocument(BaseModel):
    candidate_id: str
    source_url: str
    title: str
    body: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedHotItem(BaseModel):
    source_id: str
    external_id: str
    canonical_url: str
    title: str
    summary: str
    published_at: datetime | None = None
    author: str | None = None
    content_type: str = "article"
    tags: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    raw_ref: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class CollectRequest(BaseModel):
    source_id: str
    limit: int = Field(default=20, ge=1, le=200)
    dry_run: bool = True
    resume: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectEvent(BaseModel):
    node: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class CollectRunSummary(BaseModel):
    discovered_count: int = 0
    hydrated_count: int = 0
    normalized_count: int = 0
    persisted_count: int = 0


class CollectWorkflowState(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    request: CollectRequest
    source: SourceConfig | None = None
    status: CollectorRunStatus = CollectorRunStatus.PENDING
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    discovered_candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    hydrated_documents: list[SourceDocument] = Field(default_factory=list)
    normalized_items: list[NormalizedHotItem] = Field(default_factory=list)
    summary: CollectRunSummary = Field(default_factory=CollectRunSummary)
    events: list[CollectEvent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def log(self, node: str, message: str, **payload: Any) -> None:
        self.events.append(CollectEvent(node=node, message=message, payload=payload))
        self.touch()


class CollectGraphState(dict):
    snapshot: CollectWorkflowState


class SourceAdapter(Protocol):
    adapter_kind: str

    async def discover(
        self,
        source: SourceConfig,
        request: CollectRequest,
        checkpoint: dict[str, Any],
    ) -> list[DiscoveryCandidate]: ...

    async def hydrate(
        self,
        source: SourceConfig,
        candidates: list[DiscoveryCandidate],
    ) -> list[SourceDocument]: ...

    async def normalize(
        self,
        source: SourceConfig,
        documents: list[SourceDocument],
    ) -> list[NormalizedHotItem]: ...
