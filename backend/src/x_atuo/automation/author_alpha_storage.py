from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from x_atuo.automation import author_alpha_read_model
from x_atuo.automation import author_alpha_author_store
from x_atuo.automation import author_alpha_engagement_ledger
from x_atuo.automation import author_alpha_execution_ledger
from x_atuo.automation import author_alpha_schema
from x_atuo.automation import author_alpha_score_snapshot
from x_atuo.automation import author_alpha_sync_ledger
from x_atuo.automation.storage import utcnow

_UNSET = object()


class AuthorAlphaStorage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser().resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            author_alpha_schema.initialize_author_alpha_storage_schema(connection)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

    def has_table(self, table_name: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                (table_name,),
            ).fetchone()
        return row is not None

    def upsert_author(
        self,
        *,
        screen_name: str,
        author_name: str | None,
        rest_id: str | None,
        author_score: float,
        reply_count_7d: int,
        impressions_total_7d: int,
        avg_impressions_7d: float,
        max_impressions_7d: int,
        last_replied_at: str | None,
        last_post_seen_at: str | None,
        last_scored_at: str | None,
        source: str | None,
    ) -> None:
        author_alpha_author_store.upsert_author(
            self,
            screen_name=screen_name,
            author_name=author_name,
            rest_id=rest_id,
            author_score=author_score,
            reply_count_7d=reply_count_7d,
            impressions_total_7d=impressions_total_7d,
            avg_impressions_7d=avg_impressions_7d,
            max_impressions_7d=max_impressions_7d,
            last_replied_at=last_replied_at,
            last_post_seen_at=last_post_seen_at,
            last_scored_at=last_scored_at,
            source=source,
        )

    def list_authors_ordered_by_score(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return author_alpha_author_store.list_authors_ordered_by_score(self, limit=limit)

    def count_authors(self) -> int:
        return author_alpha_author_store.count_authors(self)

    def export_score_snapshot(self) -> dict[str, Any]:
        return author_alpha_score_snapshot.export_score_snapshot(self)

    def import_score_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        return author_alpha_score_snapshot.import_score_snapshot(
            self,
            snapshot,
            replace_existing=replace_existing,
        )

    def list_sync_checkpoints(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM alpha_sync_checkpoints
                ORDER BY sync_scope ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_engagements(self) -> list[dict[str, Any]]:
        return author_alpha_engagement_ledger.list_engagements(self)

    def list_execution_runs(self) -> list[dict[str, Any]]:
        return author_alpha_execution_ledger.list_execution_runs(self)

    def list_execution_audit_events(self) -> list[dict[str, Any]]:
        return author_alpha_execution_ledger.list_execution_audit_events(self)

    def get_execution_audit_events_for_run(self, run_id: str) -> list[dict[str, Any]]:
        return author_alpha_execution_ledger.get_execution_audit_events_for_run(self, run_id)

    def upsert_reply_daily_metrics(
        self,
        *,
        metric_date: str,
        reply_tweet_id: str,
        target_tweet_id: str | None,
        target_author: str | None,
        impressions: int,
        likes: int,
        replies: int,
        reposts: int,
        sampled_at: str,
    ) -> None:
        author_alpha_read_model.upsert_reply_daily_metrics(
            self,
            metric_date=metric_date,
            reply_tweet_id=reply_tweet_id,
            target_tweet_id=target_tweet_id,
            target_author=target_author,
            impressions=impressions,
            likes=likes,
            replies=replies,
            reposts=reposts,
            sampled_at=sampled_at,
        )

    def upsert_author_daily_rollup(
        self,
        *,
        metric_date: str,
        target_author: str,
        reply_count: int,
        impressions_total: int,
        likes_total: int,
        replies_total: int,
        reposts_total: int,
        avg_impressions: float,
        max_impressions: int,
        computed_at: str,
    ) -> None:
        author_alpha_read_model.upsert_author_daily_rollup(
            self,
            metric_date=metric_date,
            target_author=target_author,
            reply_count=reply_count,
            impressions_total=impressions_total,
            likes_total=likes_total,
            replies_total=replies_total,
            reposts_total=reposts_total,
            avg_impressions=avg_impressions,
            max_impressions=max_impressions,
            computed_at=computed_at,
        )

    def replace_day_sync_snapshot(
        self,
        *,
        metric_date: str,
        reply_metrics: list[dict[str, Any]],
        author_rollups: list[dict[str, Any]],
    ) -> None:
        author_alpha_read_model.replace_day_sync_snapshot(
            self,
            metric_date=metric_date,
            reply_metrics=reply_metrics,
            author_rollups=author_rollups,
        )

    def record_sync_run(
        self,
        *,
        run_id: str,
        run_type: str,
        status: str,
        from_date: str | None,
        to_date: str | None,
        current_date: str | None,
        days_completed: int,
        days_total: int,
        resume_from_date: str | None,
        error: str | None = None,
        created_at: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        author_alpha_sync_ledger.record_sync_run(
            self,
            run_id=run_id,
            run_type=run_type,
            status=status,
            from_date=from_date,
            to_date=to_date,
            current_date=current_date,
            days_completed=days_completed,
            days_total=days_total,
            resume_from_date=resume_from_date,
            error=error,
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
        )

    def update_sync_run(
        self,
        run_id: str,
        *,
        status: str | object = _UNSET,
        current_date: str | object = _UNSET,
        days_completed: int | object = _UNSET,
        days_total: int | object = _UNSET,
        resume_from_date: str | None | object = _UNSET,
        error: str | None | object = _UNSET,
        started_at: str | object = _UNSET,
        finished_at: str | object = _UNSET,
    ) -> None:
        updates: dict[str, Any] = {}
        if status is not _UNSET:
            updates["status"] = status
        if current_date is not _UNSET:
            updates["current_date"] = current_date
        if days_completed is not _UNSET:
            updates["days_completed"] = days_completed
        if days_total is not _UNSET:
            updates["days_total"] = days_total
        if resume_from_date is not _UNSET:
            updates["resume_from_date"] = resume_from_date
        if error is not _UNSET:
            updates["error"] = error
        if started_at is not _UNSET:
            updates["started_at"] = started_at
        if finished_at is not _UNSET:
            updates["finished_at"] = finished_at
        author_alpha_sync_ledger.update_sync_run(self, run_id, **updates)

    def clear_stale_running_sync_runs(self, *, reason: str) -> list[str]:
        return author_alpha_sync_ledger.clear_stale_running_sync_runs(self, reason=reason)

    def create_execution_run(
        self,
        *,
        run_id: str,
        job_id: str,
        job_type: str,
        endpoint: str,
        request_payload: dict[str, Any],
        status: str = "queued",
    ) -> None:
        author_alpha_execution_ledger.create_execution_run(
            self,
            run_id=run_id,
            job_id=job_id,
            job_type=job_type,
            endpoint=endpoint,
            request_payload=request_payload,
            status=status,
        )

    def update_execution_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        response_payload: Any = None,
        error: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        author_alpha_execution_ledger.update_execution_run(
            self,
            run_id,
            status=status,
            response_payload=response_payload,
            error=error,
            started_at=started_at,
            finished_at=finished_at,
        )

    def add_execution_audit_event(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: Any = None,
        level: str = "info",
        node: str | None = None,
    ) -> int:
        return author_alpha_execution_ledger.add_execution_audit_event(
            self,
            run_id=run_id,
            event_type=event_type,
            payload=payload,
            level=level,
            node=node,
        )

    def read_checkpoint(self, sync_scope: str) -> dict[str, Any] | None:
        return author_alpha_sync_ledger.read_checkpoint(self, sync_scope)

    def write_checkpoint(
        self,
        *,
        sync_scope: str,
        last_completed_date: str | None,
        next_pending_date: str | None,
        last_run_id: str | None,
        updated_at: str | None = None,
    ) -> None:
        author_alpha_sync_ledger.write_checkpoint(
            self,
            sync_scope=sync_scope,
            last_completed_date=last_completed_date,
            next_pending_date=next_pending_date,
            last_run_id=last_run_id,
            updated_at=updated_at,
        )

    def record_engagement(
        self,
        *,
        run_id: str,
        target_author: str,
        target_tweet_id: str,
        target_tweet_url: str | None,
        reply_tweet_id: str,
        reply_url: str | None,
        burst_id: str | None = None,
        burst_index: int | None = None,
        burst_size: int | None = None,
        metric_date: str | None = None,
        created_at: str | None = None,
    ) -> None:
        author_alpha_engagement_ledger.record_engagement(
            self,
            run_id=run_id,
            target_author=target_author,
            target_tweet_id=target_tweet_id,
            target_tweet_url=target_tweet_url,
            reply_tweet_id=reply_tweet_id,
            reply_url=reply_url,
            burst_id=burst_id,
            burst_index=burst_index,
            burst_size=burst_size,
            metric_date=metric_date,
            created_at=created_at,
        )

    def update_burst_size(self, *, burst_id: str, burst_size: int) -> None:
        author_alpha_engagement_ledger.update_burst_size(self, burst_id=burst_id, burst_size=burst_size)

    def get_target_success_count(self, target_tweet_id: str) -> int:
        return author_alpha_engagement_ledger.get_target_success_count(self, target_tweet_id)

    def get_target_last_success_at(self, target_tweet_id: str) -> str | None:
        return author_alpha_engagement_ledger.get_target_last_success_at(self, target_tweet_id)

    def get_author_daily_success_count(self, target_author: str, *, metric_date: str) -> int:
        return author_alpha_engagement_ledger.get_author_daily_success_count(self, target_author, metric_date=metric_date)

    def get_daily_success_count(self, *, metric_date: str) -> int:
        return author_alpha_engagement_ledger.get_daily_success_count(self, metric_date=metric_date)

    def get_recent_success_count_15m(self, as_of: str | None = None) -> int:
        return author_alpha_engagement_ledger.get_recent_success_count_15m(self, as_of=as_of)

    def zero_out_stale_authors(self, scored_screen_names: set[str], *, scored_at: str) -> int:
        return author_alpha_author_store.zero_out_stale_authors(
            self,
            scored_screen_names,
            scored_at=scored_at,
        )

    def get_reply_daily_metric(
        self, metric_date: str, reply_tweet_id: str
    ) -> dict[str, Any] | None:
        return author_alpha_read_model.get_reply_daily_metric(self, metric_date, reply_tweet_id)

    def get_author_daily_rollup(
        self, metric_date: str, target_author: str
    ) -> dict[str, Any] | None:
        return author_alpha_read_model.get_author_daily_rollup(self, metric_date, target_author)

    def list_author_daily_rollups(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return author_alpha_read_model.list_author_daily_rollups(self, start_date, end_date)

    def list_reply_daily_metrics(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return author_alpha_read_model.list_reply_daily_metrics(self, start_date, end_date)

    def get_sync_run(self, run_id: str) -> dict[str, Any] | None:
        return author_alpha_sync_ledger.get_sync_run(self, run_id)

    def get_execution_run(self, run_id: str) -> dict[str, Any] | None:
        return author_alpha_execution_ledger.get_execution_run(self, run_id)

    def list_sync_runs(self, *, limit: int | None = 20) -> list[dict[str, Any]]:
        return author_alpha_sync_ledger.list_sync_runs(self, limit=limit)

    def get_active_sync_run(self) -> dict[str, Any] | None:
        return author_alpha_sync_ledger.get_active_sync_run(self)

    def count_reply_daily_metrics(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM alpha_reply_daily_metrics"
            ).fetchone()
        return int(row["count"]) if row else 0

    def count_author_daily_rollups(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM alpha_author_daily_rollups"
            ).fetchone()
        return int(row["count"]) if row else 0

    def reset_all(self) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM alpha_run_audit_events")
            connection.execute("DELETE FROM alpha_runs")
            connection.execute("DELETE FROM alpha_engagements")
            connection.execute("DELETE FROM alpha_sync_checkpoints")
            connection.execute("DELETE FROM alpha_sync_runs")
            connection.execute("DELETE FROM alpha_author_daily_rollups")
            connection.execute("DELETE FROM alpha_reply_daily_metrics")
            connection.execute("DELETE FROM alpha_authors")


