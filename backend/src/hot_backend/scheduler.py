"""RSS collection scheduler."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from hot_backend.collectors.graph import build_hot_collect_graph, make_collect_state
from hot_backend.collectors.models import CollectRequest
from hot_backend.collectors.registry import SourceAdapterRegistry
from hot_backend.collectors.sources.mock_source import MockHotSourceAdapter
from hot_backend.collectors.sources.rss_generic import RssGenericSourceAdapter
from hot_backend.sqlite_store import get_store

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
scheduler_job_id = "rss_collector"
_scheduler_started = False


def get_registry() -> SourceAdapterRegistry:
    """Get the source adapter registry."""
    registry = SourceAdapterRegistry()
    registry.register(MockHotSourceAdapter())
    registry.register(RssGenericSourceAdapter())
    return registry


async def run_collection() -> dict:
    """Run collection for all enabled RSS sources."""
    store = get_store()
    registry = get_registry()
    graph = build_hot_collect_graph(registry=registry, store=store)

    # Get all enabled sources
    sources = store.list_sources()
    rss_sources = [s for s in sources if s.get("enabled") and s.get("adapter_kind") == "rss-generic"]

    results = []
    for source in rss_sources:
        try:
            request = CollectRequest(
                source_id=source["source_id"],
                dry_run=False,
                limit=10,
            )
            initial_state = make_collect_state(request)
            store.create_collector_run(initial_state["snapshot"].run_id, request)
            result = await graph.ainvoke(initial_state)
            snapshot = result["snapshot"]
            store.complete_collector_run(snapshot)
            results.append({
                "source_id": source["source_id"],
                "status": snapshot.status,
                "persisted": snapshot.summary.persisted_count,
            })
            logger.info(f"Collected {source['source_id']}: {snapshot.status}, {snapshot.summary.persisted_count} items")
        except Exception as e:
            logger.error(f"Failed to collect {source['source_id']}: {e}")
            results.append({
                "source_id": source["source_id"],
                "status": "failed",
                "error": str(e),
            })

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "sources_count": len(rss_sources),
        "results": results,
    }


async def scheduled_collection():
    """Scheduled collection job."""
    store = get_store()

    # Update last_run_at before starting
    now = datetime.now(timezone.utc).isoformat()
    schedule = store.get_collector_schedule()
    store.update_collector_schedule({"last_run_at": now, "last_run_status": "running"})

    try:
        result = await run_collection()

        # Calculate next run time
        interval = schedule.get("interval_minutes", 60)
        next_run = datetime.now(timezone.utc) + timedelta(minutes=interval)

        store.update_collector_schedule({
            "last_run_status": json.dumps(result, ensure_ascii=False),
            "next_run_at": next_run.isoformat(),
        })
        logger.info(f"Scheduled collection completed: {result['sources_count']} sources")
    except Exception as e:
        logger.error(f"Scheduled collection failed: {e}")
        store.update_collector_schedule({"last_run_status": json.dumps({"error": str(e)}, ensure_ascii=False)})


def ensure_scheduler_started():
    """Ensure the scheduler is started (call from async context)."""
    global _scheduler_started
    if not _scheduler_started and not scheduler.running:
        try:
            scheduler.start()
            _scheduler_started = True
            logger.info("Scheduler started")
        except RuntimeError:
            # No event loop yet, will start later
            pass


def start_scheduler():
    """Start the scheduler if enabled."""
    store = get_store()
    schedule = store.get_collector_schedule()

    if not schedule.get("enabled"):
        logger.info("Scheduler is disabled")
        return

    interval_minutes = schedule.get("interval_minutes", 60)

    if scheduler.get_job(scheduler_job_id):
        scheduler.remove_job(scheduler_job_id)

    scheduler.add_job(
        scheduled_collection,
        IntervalTrigger(minutes=interval_minutes),
        id=scheduler_job_id,
        replace_existing=True,
    )

    ensure_scheduler_started()
    logger.info(f"Scheduler configured with {interval_minutes} minute interval")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.get_job(scheduler_job_id):
        scheduler.remove_job(scheduler_job_id)
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def update_scheduler_config(enabled: bool | None = None, interval_minutes: int | None = None) -> dict:
    """Update scheduler configuration (sync version - just updates DB)."""
    store = get_store()

    updates = {}
    if enabled is not None:
        updates["enabled"] = enabled
    if interval_minutes is not None:
        updates["interval_minutes"] = interval_minutes

    store.update_collector_schedule(updates)

    # Get updated config
    schedule = store.get_collector_schedule()

    # Calculate next run time if enabling
    if schedule.get("enabled") and interval_minutes:
        next_run = datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
        store.update_collector_schedule({"next_run_at": next_run.isoformat()})
    elif not schedule.get("enabled"):
        store.update_collector_schedule({"next_run_at": None})

    return store.get_collector_schedule()


async def apply_scheduler_config():
    """Apply scheduler config (must be called from async context)."""
    store = get_store()
    schedule = store.get_collector_schedule()

    if schedule.get("enabled"):
        interval = schedule.get("interval_minutes", 60)
        next_run = datetime.now(timezone.utc) + timedelta(minutes=interval)

        if scheduler.get_job(scheduler_job_id):
            scheduler.remove_job(scheduler_job_id)

        scheduler.add_job(
            scheduled_collection,
            IntervalTrigger(minutes=interval),
            id=scheduler_job_id,
            replace_existing=True,
        )

        if not scheduler.running:
            scheduler.start()
            logger.info(f"Scheduler started with {interval}min interval")
        store.update_collector_schedule({"next_run_at": next_run.isoformat()})
    else:
        if scheduler.get_job(scheduler_job_id):
            scheduler.remove_job(scheduler_job_id)
        store.update_collector_schedule({"next_run_at": None})
        logger.info("Scheduler disabled")
