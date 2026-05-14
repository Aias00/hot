from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from x_atuo.automation.api_execution_services import (
    _dispatch_scheduled_request,
    _record_dropped_scheduled_request,
)
from x_atuo.automation.api_routes import register_routes
from x_atuo.automation.api_sync_services import (
    _backfill_author_alpha_shared_engagements,
    _build_author_alpha_sync_manager,
    _build_scheduled_author_alpha,
    _build_scheduled_author_alpha_reconcile,
    _build_scheduled_feed_engage,
    _dispatch_scheduled_author_alpha_reconcile,
    _resolve_author_alpha_db_path,
    _resolve_db_path,
)
from x_atuo.automation.author_alpha_storage import AuthorAlphaStorage
from x_atuo.automation.config import AutomationConfig
from x_atuo.automation.observability import build_langfuse_runtime
from x_atuo.automation.scheduler import AutomationScheduler
from x_atuo.automation.storage import AutomationStorage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AutomationConfig()
    storage = AutomationStorage(_resolve_db_path())
    author_alpha_storage = AuthorAlphaStorage(_resolve_author_alpha_db_path(settings))
    observability_runtime = build_langfuse_runtime(settings)
    storage.initialize()
    author_alpha_storage.initialize()
    storage.clear_stale_running_runs(reason="stale running cleared on service startup")
    author_alpha_storage.clear_stale_running_sync_runs(reason="stale running cleared on service startup")
    _backfill_author_alpha_shared_engagements(author_alpha_storage=author_alpha_storage, storage=storage)
    app.state.storage = storage
    app.state.author_alpha_storage = author_alpha_storage
    app.state.settings = settings
    app.state.observability_runtime = observability_runtime
    author_alpha_sync_manager = _build_author_alpha_sync_manager(settings, author_alpha_storage)
    app.state.author_alpha_sync_manager = author_alpha_sync_manager

    scheduler = AutomationScheduler(
        settings.scheduler,
        lambda request_obj: _dispatch_scheduled_request(
            request_obj,
            storage,
            author_alpha_storage,
            settings=settings,
            observability_runtime=observability_runtime,
        ),
        on_queue_full=lambda request_obj: _record_dropped_scheduled_request(
            request_obj,
            storage,
            author_alpha_storage=author_alpha_storage,
            reason="scheduler backlog full",
        ),
    )
    reconcile_scheduler_holder: dict[str, AutomationScheduler] = {}
    reconcile_scheduler = AutomationScheduler(
        settings.scheduler,
        lambda request_obj: _dispatch_scheduled_author_alpha_reconcile(
            request_obj,
            settings=settings,
            manager=author_alpha_sync_manager,
            scheduler=reconcile_scheduler_holder["scheduler"],
        ),
    )
    reconcile_scheduler_holder["scheduler"] = reconcile_scheduler
    definitions = [
        ("scheduled_feed_engage", _build_scheduled_feed_engage(settings)),
        ("scheduled_author_alpha_engage", _build_scheduled_author_alpha(settings)),
    ]
    for attr_name, definition in definitions:
        if definition is None:
            continue
        scheduler.register_job(definition)
        setattr(app.state, attr_name, definition)
    reconcile_definition = _build_scheduled_author_alpha_reconcile(settings)
    if reconcile_definition is not None:
        reconcile_scheduler.register_job(reconcile_definition)
        app.state.scheduled_author_alpha_reconcile = reconcile_definition
    app.state.scheduler = scheduler
    app.state.author_alpha_reconcile_scheduler = reconcile_scheduler
    scheduler.maybe_start()
    reconcile_scheduler.maybe_start()
    try:
        yield
    finally:
        try:
            reconcile_scheduler.shutdown(wait=False)
        finally:
            try:
                scheduler.shutdown(wait=False)
            finally:
                observability_runtime.shutdown()


def build_app(*, title: str = "x-atuo automation API") -> FastAPI:
    app = FastAPI(title=title, lifespan=lifespan)
    register_routes(app)
    return app
