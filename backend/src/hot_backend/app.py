from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from x_atuo.automation.api import register_routes as register_automation_routes
from x_atuo.automation.api_bootstrap import lifespan as automation_lifespan

from hot_backend.admin_routes import router as admin_router
from hot_backend.collectors.api import router as collect_router
from hot_backend.collectors.graph import build_hot_collect_graph
from hot_backend.collectors.registry import SourceAdapterRegistry
from hot_backend.collectors.sources.mock_source import MockHotSourceAdapter
from hot_backend.collectors.sources.mp_hot_snapshot import MpHotSnapshotSourceAdapter
from hot_backend.collectors.sources.rss_generic import RssGenericSourceAdapter
from hot_backend.routes import router as hot_router
from hot_backend.scheduler import apply_scheduler_config, stop_scheduler
from hot_backend.sqlite_store import get_store


@asynccontextmanager
async def hot_lifespan(app):
    async with automation_lifespan(app):
        await apply_scheduler_config()
        try:
            yield
        finally:
            stop_scheduler()


def create_app():
    app = FastAPI(title="hot backend", lifespan=hot_lifespan)
    register_automation_routes(app)
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
