from __future__ import annotations

import asyncio
import json
import sys

from hot_backend.collectors.graph import build_hot_collect_graph, make_collect_state
from hot_backend.collectors.models import CollectRequest
from hot_backend.collectors.registry import SourceAdapterRegistry
from hot_backend.collectors.sources.mock_source import MockHotSourceAdapter
from hot_backend.collectors.sources.rss_generic import RssGenericSourceAdapter
from hot_backend.sqlite_store import DEFAULT_RSS_SOURCE_IDS, get_store


async def main() -> int:
    store = get_store()
    registry = SourceAdapterRegistry()
    registry.register(MockHotSourceAdapter())
    registry.register(RssGenericSourceAdapter())
    graph = build_hot_collect_graph(registry=registry, store=store)

    source_ids = list(DEFAULT_RSS_SOURCE_IDS)

    results = []
    for source_id in source_ids:
        try:
            request = CollectRequest(
                source_id=source_id,
                dry_run=False,
                limit=10,
            )
            initial_state = make_collect_state(request)
            store.create_collector_run(initial_state["snapshot"].run_id, request)
            result = await graph.ainvoke(initial_state)
            snapshot = result["snapshot"]
            store.complete_collector_run(snapshot)
            results.append(
                {
                    "source_id": source_id,
                    "status": snapshot.status,
                    "summary": snapshot.summary.model_dump(mode="json"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "source_id": source_id,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
