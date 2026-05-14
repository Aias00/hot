from __future__ import annotations

from langgraph.graph import END, StateGraph

from hot_backend.collectors.enrichment import enrich_item
from hot_backend.collectors.models import (
    CollectRequest,
    CollectWorkflowState,
    CollectorRunStatus,
)
from hot_backend.collectors.registry import SourceAdapterRegistry
from hot_backend.sqlite_store import HotSQLiteStore


def make_collect_state(request: CollectRequest) -> dict:
    snapshot = CollectWorkflowState(request=request, status=CollectorRunStatus.RUNNING)
    snapshot.log("graph", "collection workflow started")
    return {"snapshot": snapshot}


def build_hot_collect_graph(
    *,
    registry: SourceAdapterRegistry,
    store: HotSQLiteStore,
):
    graph = StateGraph(dict)

    async def resolve_source(state: dict) -> dict:
        snapshot: CollectWorkflowState = state["snapshot"]
        source = store.get_collector_source(snapshot.request.source_id)
        snapshot.source = source
        snapshot.checkpoint = store.get_collector_checkpoint(source.source_id)
        snapshot.log("resolve_source", "resolved collector source", source_id=source.source_id)
        return {"snapshot": snapshot}

    async def discover_candidates(state: dict) -> dict:
        snapshot: CollectWorkflowState = state["snapshot"]
        adapter = registry.get(snapshot.source.adapter_kind)
        snapshot.discovered_candidates = await adapter.discover(
            snapshot.source,
            snapshot.request,
            snapshot.checkpoint,
        )
        snapshot.summary.discovered_count = len(snapshot.discovered_candidates)
        source_modes: dict[str, int] = {}
        seed_urls: list[str] = []
        for candidate in snapshot.discovered_candidates:
            mode = candidate.metadata.get("source_mode")
            if mode:
                source_modes[mode] = source_modes.get(mode, 0) + 1
            seed_url = candidate.metadata.get("seed_url")
            if seed_url and seed_url not in seed_urls:
                seed_urls.append(seed_url)
        snapshot.log(
            "discover_candidates",
            "discovered candidates",
            count=len(snapshot.discovered_candidates),
            source_modes=source_modes,
            seed_urls=seed_urls,
        )
        return {"snapshot": snapshot}

    async def hydrate_documents(state: dict) -> dict:
        snapshot: CollectWorkflowState = state["snapshot"]
        adapter = registry.get(snapshot.source.adapter_kind)
        snapshot.hydrated_documents = await adapter.hydrate(
            snapshot.source,
            snapshot.discovered_candidates,
        )
        snapshot.summary.hydrated_count = len(snapshot.hydrated_documents)
        snapshot.log("hydrate_documents", "hydrated documents", count=len(snapshot.hydrated_documents))
        return {"snapshot": snapshot}

    async def normalize_items(state: dict) -> dict:
        snapshot: CollectWorkflowState = state["snapshot"]
        adapter = registry.get(snapshot.source.adapter_kind)
        snapshot.normalized_items = await adapter.normalize(
            snapshot.source,
            snapshot.hydrated_documents,
        )
        snapshot.summary.normalized_count = len(snapshot.normalized_items)
        snapshot.log("normalize_items", "normalized items", count=len(snapshot.normalized_items))
        return {"snapshot": snapshot}

    async def enrich_items(state: dict) -> dict:
        snapshot: CollectWorkflowState = state["snapshot"]
        snapshot.normalized_items = [
            enrich_item(snapshot.source, item)
            for item in snapshot.normalized_items
        ]
        snapshot.log(
            "enrich_items",
            "enriched normalized items",
            count=len(snapshot.normalized_items),
            categories=sorted(
                {
                    item.metrics.get("source_category", "generic")
                    for item in snapshot.normalized_items
                }
            ),
        )
        return {"snapshot": snapshot}

    async def persist_items(state: dict) -> dict:
        snapshot: CollectWorkflowState = state["snapshot"]
        persisted_count = 0
        if not snapshot.request.dry_run:
            persisted_count = store.persist_hot_items(snapshot.normalized_items)
            store.upsert_collector_checkpoint(
                snapshot.source.source_id,
                {
                  "latest_external_id": snapshot.normalized_items[-1].external_id
                  if snapshot.normalized_items
                  else None
                },
            )
        snapshot.summary.persisted_count = persisted_count
        snapshot.log("persist_items", "persisted normalized items", count=persisted_count, dry_run=snapshot.request.dry_run)
        return {"snapshot": snapshot}

    async def complete_run(state: dict) -> dict:
        snapshot: CollectWorkflowState = state["snapshot"]
        snapshot.status = CollectorRunStatus.COMPLETED
        snapshot.log("complete_run", "collection workflow completed", summary=snapshot.summary.model_dump(mode="json"))
        return {"snapshot": snapshot}

    graph.add_node("resolve_source", resolve_source)
    graph.add_node("discover_candidates", discover_candidates)
    graph.add_node("hydrate_documents", hydrate_documents)
    graph.add_node("normalize_items", normalize_items)
    graph.add_node("enrich_items", enrich_items)
    graph.add_node("persist_items", persist_items)
    graph.add_node("complete_run", complete_run)

    graph.set_entry_point("resolve_source")
    graph.add_edge("resolve_source", "discover_candidates")
    graph.add_edge("discover_candidates", "hydrate_documents")
    graph.add_edge("hydrate_documents", "normalize_items")
    graph.add_edge("normalize_items", "enrich_items")
    graph.add_edge("enrich_items", "persist_items")
    graph.add_edge("persist_items", "complete_run")
    graph.add_edge("complete_run", END)

    return graph.compile()
