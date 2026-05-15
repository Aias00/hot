from __future__ import annotations

from x_atuo.automation.api import build_app as build_x_atuo_app

from hot_backend.admin_routes import router as admin_router
from hot_backend.collectors.api import router as collect_router
from hot_backend.collectors.graph import build_hot_collect_graph
from hot_backend.collectors.registry import SourceAdapterRegistry
from hot_backend.collectors.sources.mock_source import MockHotSourceAdapter
from hot_backend.collectors.sources.mp_hot_snapshot import MpHotSnapshotSourceAdapter
from hot_backend.collectors.sources.rss_generic import RssGenericSourceAdapter
from hot_backend.routes import router as hot_router
from hot_backend.sqlite_store import get_store


def create_app():
    app = build_x_atuo_app(title="hot backend")
    hot_store = get_store()
    registry = SourceAdapterRegistry()
    registry.register(MockHotSourceAdapter())
    registry.register(MpHotSnapshotSourceAdapter())
    registry.register(RssGenericSourceAdapter())
    app.state.hot_store = hot_store
    app.state.collector_registry = registry
    app.state.hot_collect_graph = build_hot_collect_graph(
        registry=registry,
        store=hot_store,
    )

    app.include_router(hot_router)
    app.include_router(collect_router)
    app.include_router(admin_router)
    return app


app = create_app()
