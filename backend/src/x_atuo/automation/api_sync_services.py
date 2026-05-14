from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import Request

from x_atuo.automation.author_alpha_storage import AuthorAlphaStorage
from x_atuo.automation.author_alpha_sync import AuthorAlphaSync, AuthorAlphaSyncActiveError, AuthorAlphaSyncManager
from x_atuo.automation.config import AutomationConfig
from x_atuo.automation.scheduler import AutomationScheduler, ScheduledWorkflow
from x_atuo.automation.state import AutomationRequest, FeedOptions, WorkflowKind
from x_atuo.automation.storage import AutomationStorage
from x_atuo.core.twitter_client import TwitterClient
from x_atuo.core.x_web_analytics import XWebAnalyticsClient

logger = logging.getLogger(__name__)


def _resolve_db_path() -> Path:
    return Path(os.getenv("X_ATUO_DB_PATH", "data/x_atuo.sqlite3"))


def _resolve_author_alpha_db_path(settings: AutomationConfig) -> Path:
    return Path(settings.author_alpha.db_path).expanduser()


def _author_alpha_shared_rows(storage: AuthorAlphaStorage) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in storage.list_engagements():
        rows.append(
            {
                "run_id": row.get("run_id"),
                "target_tweet_id": row.get("target_tweet_id"),
                "target_author": row.get("target_author"),
                "target_tweet_url": row.get("target_tweet_url"),
                "reply_tweet_id": row.get("reply_tweet_id"),
                "reply_url": row.get("reply_url"),
                "followed": False,
                "created_at": row.get("created_at"),
            }
        )
    return rows


def _backfill_author_alpha_shared_engagements(
    *,
    author_alpha_storage: AuthorAlphaStorage,
    storage: AutomationStorage,
) -> int:
    importer = getattr(storage, "import_shared_engagements", None)
    engagement_reader = getattr(author_alpha_storage, "list_engagements", None)
    if not callable(importer) or not callable(engagement_reader):
        return 0
    rows = _author_alpha_shared_rows(author_alpha_storage)
    if not rows:
        return 0
    return storage.import_shared_engagements(
        workflow=WorkflowKind.AUTHOR_ALPHA_ENGAGE.value,
        rows=rows,
        replace_existing=False,
    )


def _snapshot_db_file(path: Path) -> tuple[bool, bytes | None]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return False, None
    return True, resolved.read_bytes()


def _restore_db_file(path: Path, snapshot: tuple[bool, bytes | None]) -> None:
    existed, payload = snapshot
    resolved = path.expanduser().resolve()
    if existed:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        if payload is None:
            raise RuntimeError("database snapshot payload missing for existing file")
        with NamedTemporaryFile(dir=resolved.parent, delete=False) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(resolved)
    else:
        if resolved.exists():
            resolved.unlink()


class _LazyAuthorAlphaSyncManager:
    def __init__(self, *, settings: AutomationConfig, storage: AuthorAlphaStorage) -> None:
        self.settings = settings
        self.storage = storage
        self._manager: AuthorAlphaSyncManager | None = None

    def _build_runtime_manager(self) -> AuthorAlphaSyncManager:
        analytics_client = XWebAnalyticsClient.from_settings(self.settings)
        twitter_client = TwitterClient.from_config(
            self.settings.agent_reach_config_path,
            proxy=self.settings.twitter.proxy_url,
            timeout=max(30, self.settings.author_alpha.posts_per_author * 30),
        )
        sync = AuthorAlphaSync(
            storage=self.storage,
            analytics_client=analytics_client,
            twitter_client=twitter_client,
            timezone=self.settings.author_alpha.timezone,
            excluded_authors=self.settings.author_alpha.excluded_authors,
            score_lookback_days=self.settings.author_alpha.score_lookback_days,
            score_min_daily_replies=self.settings.author_alpha.score_min_daily_replies,
            score_prior_weight=self.settings.author_alpha.score_prior_weight,
            score_penalty_constant=self.settings.author_alpha.score_penalty_constant,
        )
        return AuthorAlphaSyncManager(storage=self.storage, sync=sync)

    def _delegate(self) -> AuthorAlphaSyncManager:
        if self._manager is None:
            self._manager = self._build_runtime_manager()
        return self._manager

    def start_bootstrap(self, **kwargs: Any) -> dict[str, object]:
        return self._delegate().start_bootstrap(**kwargs)

    def start_reconcile(self, **kwargs: Any) -> dict[str, object]:
        return self._delegate().start_reconcile(**kwargs)

    def stop_active_run(self) -> dict[str, object]:
        if self._manager is not None:
            return self._manager.stop_active_run()
        active_run = self.storage.get_active_sync_run()
        if active_run is None:
            raise AuthorAlphaSyncActiveError("no active author-alpha sync run")
        return self._delegate().stop_active_run()

    def get_status(self) -> dict[str, object]:
        active_run = self.storage.get_active_sync_run()
        latest_runs = self.storage.list_sync_runs(limit=1)
        latest_run = latest_runs[0] if latest_runs else None
        return {
            "active": active_run is not None,
            "bootstrap_required": self.storage.count_authors() == 0,
            "active_run": active_run,
            "latest_run": active_run or latest_run,
            "bootstrap_checkpoint": self.storage.read_checkpoint("bootstrap"),
            "reconcile_checkpoint": self.storage.read_checkpoint("reconcile"),
        }

    def list_history(self, *, limit: int = 20) -> list[dict[str, object]]:
        return self.storage.list_sync_runs(limit=limit)

    def get_run(self, run_id: str) -> dict[str, object] | None:
        return self.storage.get_sync_run(run_id)


def _build_author_alpha_sync_manager(
    settings: AutomationConfig,
    storage: AuthorAlphaStorage,
) -> _LazyAuthorAlphaSyncManager:
    return _LazyAuthorAlphaSyncManager(settings=settings, storage=storage)


def _build_scheduled_feed_engage(settings: AutomationConfig) -> ScheduledWorkflow | None:
    if not (settings.scheduler.enabled and settings.scheduler.feed_engage_enabled):
        return None
    trigger = settings.scheduler.feed_engage_trigger
    trigger_args: dict[str, Any]
    if trigger == "interval":
        trigger_args = {
            "seconds": settings.scheduler.feed_engage_seconds,
            "jitter": settings.scheduler.feed_engage_jitter_seconds,
        }
    else:
        trigger_args = {"jitter": settings.scheduler.feed_engage_jitter_seconds}
        if settings.scheduler.feed_engage_minute is not None:
            trigger_args["minute"] = settings.scheduler.feed_engage_minute
        if settings.scheduler.feed_engage_hour is not None:
            trigger_args["hour"] = settings.scheduler.feed_engage_hour
        if settings.scheduler.feed_engage_day is not None:
            trigger_args["day"] = settings.scheduler.feed_engage_day
        if settings.scheduler.feed_engage_day_of_week is not None:
            trigger_args["day_of_week"] = settings.scheduler.feed_engage_day_of_week
    request_obj = AutomationRequest.for_feed_engage(
        job_name="scheduled-feed-engage",
        dry_run=False,
        approval_mode="ai_auto",
        reply_text=None,
        feed_options=FeedOptions(
            feed_type=settings.twitter.default_feed_type,
            feed_count=settings.twitter.default_feed_count,
        ),
        metadata={"proxy": settings.twitter.proxy_url, "trigger": "scheduler"},
    )
    return ScheduledWorkflow(
        job_id="scheduled-feed-engage",
        request=request_obj,
        trigger=trigger,
        trigger_args=trigger_args,
        enabled=True,
    )


def _build_scheduled_author_alpha(settings: AutomationConfig) -> ScheduledWorkflow | None:
    if not (settings.scheduler.enabled and settings.author_alpha.enabled):
        return None
    trigger = settings.author_alpha.trigger
    trigger_args: dict[str, Any]
    if trigger == "interval":
        trigger_args = {
            "seconds": settings.author_alpha.seconds,
            "jitter": settings.author_alpha.jitter_seconds,
        }
    else:
        trigger_args = {"jitter": settings.author_alpha.jitter_seconds}
        if settings.author_alpha.minute is not None:
            trigger_args["minute"] = settings.author_alpha.minute
        if settings.author_alpha.hour is not None:
            trigger_args["hour"] = settings.author_alpha.hour
    request_obj = AutomationRequest.for_author_alpha_engage(
        job_name="scheduled-author-alpha-engage",
        dry_run=False,
        approval_mode="ai_auto",
        metadata={"proxy": settings.twitter.proxy_url, "trigger": "scheduler"},
    )
    return ScheduledWorkflow(
        job_id="scheduled-author-alpha-engage",
        request=request_obj,
        trigger=trigger,
        trigger_args=trigger_args,
        enabled=True,
    )


def _scheduled_author_alpha_reconcile_target_date(now: datetime | None = None) -> str:
    anchor = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    return (anchor.date() - timedelta(days=1)).isoformat()


def _build_scheduled_author_alpha_reconcile(settings: AutomationConfig) -> ScheduledWorkflow | None:
    if not (
        settings.scheduler.enabled
        and settings.author_alpha.enabled
        and settings.scheduler.author_alpha_reconcile_enabled
    ):
        return None
    request_obj = AutomationRequest.for_author_alpha_reconcile(
        job_name="scheduled-author-alpha-reconcile",
        dry_run=True,
        metadata={
            "trigger": "scheduler",
            "target_date_mode": "utc_yesterday",
            "retry_delay_minutes": settings.scheduler.author_alpha_reconcile_retry_delay_minutes,
        },
    )
    return ScheduledWorkflow(
        job_id="scheduled-author-alpha-reconcile",
        request=request_obj,
        trigger="cron",
        trigger_args={
            "hour": settings.scheduler.author_alpha_reconcile_hour,
            "minute": settings.scheduler.author_alpha_reconcile_minute,
            "timezone": settings.scheduler.author_alpha_reconcile_timezone,
        },
        enabled=True,
    )


def _wait_for_author_alpha_sync_run(
    manager: AuthorAlphaSyncManager,
    run_id: str,
    *,
    timeout_seconds: float = 1800.0,
    poll_seconds: float = 0.5,
) -> dict[str, object] | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = manager.get_run(run_id)
        if payload is not None and str(payload.get("status")) != "running":
            return payload
        time.sleep(poll_seconds)
    return manager.get_run(run_id)


def _is_retryable_author_alpha_sync_error(error: str | None) -> bool:
    if not error:
        return False
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "timed out",
            "timeout",
            "tls connect error",
            "curl: (35)",
            "curl: (28)",
            "ssl",
            "unexpected eof",
            "eof occurred",
            "remote end closed connection",
            "connection reset",
            "connection aborted",
            "temporarily unavailable",
            "http error 500",
            "internal server error",
        )
    )


def _schedule_author_alpha_reconcile_retry(
    *,
    scheduler: AutomationScheduler,
    target_date: str,
    retry_delay_minutes: int,
) -> None:
    retry_at = datetime.now(timezone.utc) + timedelta(minutes=max(1, retry_delay_minutes))
    scheduler.register_job(
        ScheduledWorkflow(
            job_id=f"scheduled-author-alpha-reconcile-retry-{target_date}",
            request=AutomationRequest.for_author_alpha_reconcile(
                job_name=f"scheduled-author-alpha-reconcile-retry-{target_date}",
                dry_run=True,
                metadata={
                    "trigger": "scheduler_retry",
                    "scheduled_retry": True,
                    "target_date": target_date,
                    "retry_delay_minutes": retry_delay_minutes,
                },
            ),
            trigger="date",
            trigger_args={"run_date": retry_at},
            enabled=True,
            replace_existing=True,
        )
    )


def _dispatch_scheduled_author_alpha_reconcile(
    request: AutomationRequest,
    *,
    settings: AutomationConfig,
    manager: AuthorAlphaSyncManager,
    scheduler: AutomationScheduler,
) -> None:
    target_date = str(
        request.metadata.get("target_date")
        or _scheduled_author_alpha_reconcile_target_date()
    )
    retry_delay_minutes = max(
        1,
        int(
            request.metadata.get("retry_delay_minutes")
            or settings.scheduler.author_alpha_reconcile_retry_delay_minutes
        ),
    )
    scheduled_retry = bool(request.metadata.get("scheduled_retry"))
    try:
        accepted = manager.start_reconcile(target_date=target_date)
    except AuthorAlphaSyncActiveError:
        logger.warning(
            "scheduled author-alpha reconcile skipped because another sync run is active",
            extra={"target_date": target_date, "scheduled_retry": scheduled_retry},
        )
        return

    run_id = str(accepted["run_id"])
    payload = _wait_for_author_alpha_sync_run(manager, run_id)
    if payload is None:
        logger.warning(
            "scheduled author-alpha reconcile timed out while waiting for sync completion",
            extra={"run_id": run_id, "target_date": target_date},
        )
        return
    if str(payload.get("status")) != "failed" or scheduled_retry:
        return
    error = str(payload.get("error") or "")
    if not _is_retryable_author_alpha_sync_error(error):
        return
    _schedule_author_alpha_reconcile_retry(
        scheduler=scheduler,
        target_date=target_date,
        retry_delay_minutes=retry_delay_minutes,
    )


def get_storage(request: Request) -> AutomationStorage:
    return request.app.state.storage


def get_author_alpha_storage(request: Request) -> AuthorAlphaStorage:
    return request.app.state.author_alpha_storage


def get_author_alpha_sync_manager(request: Request) -> AuthorAlphaSyncManager:
    return request.app.state.author_alpha_sync_manager


__all__ = [
    "_backfill_author_alpha_shared_engagements",
    "_build_author_alpha_sync_manager",
    "_build_scheduled_author_alpha",
    "_build_scheduled_author_alpha_reconcile",
    "_build_scheduled_feed_engage",
    "_dispatch_scheduled_author_alpha_reconcile",
    "_resolve_author_alpha_db_path",
    "_resolve_db_path",
    "_restore_db_file",
    "_scheduled_author_alpha_reconcile_target_date",
    "_snapshot_db_file",
    "get_author_alpha_storage",
    "get_author_alpha_sync_manager",
    "get_storage",
]
