from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from x_atuo.automation import automation_engagement_ledger
from x_atuo.automation import automation_run_ledger
from x_atuo.automation import storage_schema
from x_atuo.automation.state import WorkflowKind
from x_atuo.automation.utils import deserialize_json as _deserialize_json
from x_atuo.automation.utils import serialize_json as _serialize_json
from x_atuo.automation.utils import utcnow


def _strip_internal_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if not str(key).startswith("_x_atuo_")
    }


def _parse_transient_reply_failure_count(reason: str | None) -> int:
    if not isinstance(reason, str):
        return 0
    prefix = "transient reply failure #"
    text = reason.strip()
    if not text.startswith(prefix):
        return 0
    remainder = text[len(prefix):]
    count_text, _, _ = remainder.partition(":")
    try:
        return max(0, int(count_text.strip()))
    except ValueError:
        return 0


class AutomationStorage:
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
            storage_schema.initialize_automation_storage_schema(connection)

    @staticmethod
    def _release_expired_candidate_claims(connection: sqlite3.Connection, *, now: str) -> int:
        cursor = connection.execute(
            """
            UPDATE candidate_cache
            SET status = 'pending', claim_run_id = NULL, claim_expires_at = NULL, updated_ts = ?
            WHERE status = 'claimed' AND claim_expires_at IS NOT NULL AND claim_expires_at <= ? AND expires_at > ?
            """,
            (now, now, now),
        )
        return int(cursor.rowcount or 0)

    def healthcheck(self) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT 1 AS ok").fetchone()
        return {
            "status": "ok" if row and row["ok"] == 1 else "error",
            "db_path": str(self.db_path),
            "checked_at": datetime.now(timezone.utc),
        }

    def upsert_job(self, job_id: str, job_type: str, config: dict[str, Any] | None = None) -> None:
        now = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, job_type, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    job_type = excluded.job_type,
                    config_json = excluded.config_json,
                    updated_at = excluded.updated_at
                """,
                (job_id, job_type, _serialize_json(config), now, now),
            )

    def create_run(
        self,
        *,
        run_id: str,
        job_id: str,
        job_type: str,
        endpoint: str,
        request_payload: dict[str, Any],
        status: str = "queued",
    ) -> None:
        automation_run_ledger.create_run(
            self,
            run_id=run_id,
            job_id=job_id,
            job_type=job_type,
            endpoint=endpoint,
            request_payload=request_payload,
            status=status,
        )

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        response_payload: Any = None,
        error: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        automation_run_ledger.update_run(
            self,
            run_id,
            status=status,
            response_payload=response_payload,
            error=error,
            started_at=started_at,
            finished_at=finished_at,
        )

    def add_audit_event(
        self,
        *,
        run_id: str,
        event_type: str,
        payload: Any = None,
        level: str = "info",
        node: str | None = None,
    ) -> int:
        return automation_run_ledger.add_audit_event(
            self,
            run_id=run_id,
            event_type=event_type,
            payload=payload,
            level=level,
            node=node,
        )

    def clear_stale_running_runs(self, *, reason: str) -> list[str]:
        now = utcnow()
        payload_json = _serialize_json({"reason": reason})
        with self.connect() as connection:
            rows = connection.execute(
                """
                UPDATE runs
                SET status = 'failed', error = ?, finished_at = ?, updated_at = ?
                WHERE status = 'running'
                RETURNING id
                """,
                (reason, now, now),
            ).fetchall()
            cleared = [str(row["id"]) for row in rows]
            if cleared:
                connection.executemany(
                    """
                    INSERT INTO audit_events (run_id, level, event_type, node, payload_json, created_at)
                    VALUES (?, 'info', 'stale_running_cleared', 'service', ?, ?)
                    """,
                    [(run_id, payload_json, now) for run_id in cleared],
                )
        return cleared

    def cleanup_candidate_cache(self) -> int:
        now = utcnow()
        with self.connect() as connection:
            released = self._release_expired_candidate_claims(connection, now=now)
            cursor = connection.execute(
                """
                DELETE FROM candidate_cache
                WHERE expires_at <= ?
                """,
                (now,),
            )
            return released + int(cursor.rowcount or 0)

    def upsert_candidate_cache_entries(
        self,
        *,
        workflow: str,
        source_run_id: str,
        candidates: list[dict[str, Any]],
        expires_at: str,
    ) -> None:
        now = utcnow()
        with self.connect() as connection:
            for candidate in candidates:
                metadata = _strip_internal_metadata(dict(candidate.get("metadata") or {}))
                connection.execute(
                    """
                    INSERT INTO candidate_cache (
                        workflow, tweet_id, screen_name, created_at, text, metadata_json,
                        status, reason, source_run_id, claim_run_id, claim_expires_at,
                        hydrated_at, expires_at, created_ts, updated_ts
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, NULL, NULL, ?, ?, ?, ?)
                    ON CONFLICT(workflow, tweet_id) DO UPDATE SET
                        screen_name = excluded.screen_name,
                        created_at = excluded.created_at,
                        text = excluded.text,
                        metadata_json = excluded.metadata_json,
                        status = 'pending',
                        reason = NULL,
                        source_run_id = excluded.source_run_id,
                        claim_run_id = NULL,
                        claim_expires_at = NULL,
                        hydrated_at = excluded.hydrated_at,
                        expires_at = excluded.expires_at,
                        updated_ts = excluded.updated_ts
                    """,
                    (
                        workflow,
                        str(candidate.get("tweet_id") or ""),
                        candidate.get("screen_name"),
                        candidate.get("created_at"),
                        candidate.get("text"),
                        _serialize_json(metadata),
                        source_run_id,
                        now,
                        expires_at,
                        now,
                        now,
                    ),
                )

    def claim_pending_candidate_cache(
        self,
        *,
        workflow: str,
        limit: int,
        run_id: str,
        lease_expires_at: str,
    ) -> list[dict[str, Any]]:
        now = utcnow()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._release_expired_candidate_claims(connection, now=now)
            rows = connection.execute(
                """
                SELECT tweet_id
                FROM candidate_cache
                WHERE workflow = ? AND status = 'pending' AND expires_at > ?
                ORDER BY COALESCE(created_at, created_ts) DESC, updated_ts ASC
                LIMIT ?
                """,
                (workflow, now, limit),
            ).fetchall()
            tweet_ids = [str(row["tweet_id"]) for row in rows]
            if not tweet_ids:
                return []
            placeholders = ", ".join("?" for _ in tweet_ids)
            connection.execute(
                f"""
                UPDATE candidate_cache
                SET status = 'claimed', claim_run_id = ?, claim_expires_at = ?, updated_ts = ?
                WHERE workflow = ? AND tweet_id IN ({placeholders}) AND status = 'pending'
                """,
                (run_id, lease_expires_at, now, workflow, *tweet_ids),
            )
            claimed_rows = connection.execute(
                f"""
                SELECT workflow, tweet_id, screen_name, created_at, text, metadata_json,
                       status, reason, source_run_id, claim_run_id, claim_expires_at,
                       hydrated_at, expires_at, created_ts, updated_ts
                FROM candidate_cache
                WHERE workflow = ? AND claim_run_id = ? AND tweet_id IN ({placeholders})
                ORDER BY COALESCE(created_at, created_ts) DESC, updated_ts ASC
                """,
                (workflow, run_id, *tweet_ids),
            ).fetchall()
        return [
            {
                "workflow": row["workflow"],
                "tweet_id": row["tweet_id"],
                "screen_name": row["screen_name"],
                "created_at": row["created_at"],
                "text": row["text"],
                "metadata": _deserialize_json(row["metadata_json"]) or {},
                "status": row["status"],
                "reason": row["reason"],
                "source_run_id": row["source_run_id"],
                "claim_run_id": row["claim_run_id"],
                "claim_expires_at": row["claim_expires_at"],
                "hydrated_at": row["hydrated_at"],
                "expires_at": row["expires_at"],
            }
            for row in claimed_rows
        ]

    def list_pending_candidate_cache(self, *, workflow: str, limit: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT workflow, tweet_id, screen_name, created_at, text, metadata_json,
                       status, reason, source_run_id, claim_run_id, claim_expires_at,
                       hydrated_at, expires_at, created_ts, updated_ts
                FROM candidate_cache
                WHERE workflow = ? AND status = 'pending' AND expires_at > ?
                ORDER BY COALESCE(created_at, created_ts) DESC, updated_ts ASC
                LIMIT ?
                """,
                (workflow, utcnow(), limit),
            ).fetchall()
        return [
            {
                "workflow": row["workflow"],
                "tweet_id": row["tweet_id"],
                "screen_name": row["screen_name"],
                "created_at": row["created_at"],
                "text": row["text"],
                "metadata": _deserialize_json(row["metadata_json"]) or {},
                "status": row["status"],
                "reason": row["reason"],
                "source_run_id": row["source_run_id"],
                "claim_run_id": row["claim_run_id"],
                "claim_expires_at": row["claim_expires_at"],
                "hydrated_at": row["hydrated_at"],
                "expires_at": row["expires_at"],
            }
            for row in rows
        ]

    def release_claimed_candidate_cache(
        self,
        *,
        workflow: str,
        run_id: str,
        tweet_ids: list[str],
        reason_by_tweet_id: dict[str, str] | None = None,
    ) -> int:
        if not tweet_ids:
            return 0
        now = utcnow()
        placeholders = ", ".join("?" for _ in tweet_ids)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                f"""
                UPDATE candidate_cache
                SET status = 'pending', reason = NULL, claim_run_id = NULL, claim_expires_at = NULL, updated_ts = ?
                WHERE workflow = ? AND claim_run_id = ? AND status = 'claimed'
                AND tweet_id IN ({placeholders})
                """,
                [now, workflow, run_id, *tweet_ids],
            )
            released = int(cursor.rowcount or 0)
            if reason_by_tweet_id:
                tweet_id_set = set(tweet_ids)
                for tweet_id, reason in reason_by_tweet_id.items():
                    if reason and tweet_id in tweet_id_set:
                        connection.execute(
                            "UPDATE candidate_cache SET reason = ? WHERE workflow = ? AND tweet_id = ?",
                            (reason, workflow, tweet_id),
                        )
            return released

    def reject_candidate_cache(self, *, workflow: str, tweet_id: str, reason: str, expires_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE candidate_cache
                SET status = 'rejected', reason = ?, expires_at = ?, claim_run_id = NULL, claim_expires_at = NULL, updated_ts = ?
                WHERE workflow = ? AND tweet_id = ?
                """,
                (reason, expires_at, utcnow(), workflow, tweet_id),
            )

    def record_transient_candidate_failure(
        self,
        *,
        workflow: str,
        tweet_id: str,
        reason: str,
        max_pending_failures: int,
        rejected_expires_at: str,
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT reason
                FROM candidate_cache
                WHERE workflow = ? AND tweet_id = ?
                """,
                (workflow, tweet_id),
            ).fetchone()
            failure_count = _parse_transient_reply_failure_count(row["reason"] if row is not None else None) + 1
            next_reason = f"transient reply failure #{failure_count}: {reason}"
            if failure_count > max_pending_failures:
                connection.execute(
                    """
                    UPDATE candidate_cache
                    SET status = 'rejected', reason = ?, expires_at = ?, claim_run_id = NULL, claim_expires_at = NULL, updated_ts = ?
                    WHERE workflow = ? AND tweet_id = ?
                    """,
                    (next_reason, rejected_expires_at, now, workflow, tweet_id),
                )
                return {"failure_count": failure_count, "rejected": True, "reason": next_reason}

            connection.execute(
                """
                UPDATE candidate_cache
                SET status = 'pending', reason = ?, claim_run_id = NULL, claim_expires_at = NULL, updated_ts = ?
                WHERE workflow = ? AND tweet_id = ?
                """,
                (next_reason, now, workflow, tweet_id),
            )
            return {"failure_count": failure_count, "rejected": False, "reason": next_reason}

    def consume_candidate_cache(self, *, workflow: str, tweet_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM candidate_cache WHERE workflow = ? AND tweet_id = ?",
                (workflow, tweet_id),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return automation_run_ledger.get_run(self, run_id)

    def has_dedupe_key(self, dedupe_key: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT dedupe_key FROM dedupe_keys WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
        return row is not None

    def store_dedupe_key(self, dedupe_key: str, scope: str, expires_at: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO dedupe_keys (dedupe_key, scope, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (dedupe_key, scope, utcnow(), expires_at),
            )

    def record_engagement(
        self,
        *,
        run_id: str,
        target_tweet_id: str | None,
        target_author: str | None,
        target_tweet_url: str | None,
        reply_tweet_id: str | None,
        reply_url: str | None,
        followed: bool,
    ) -> None:
        automation_engagement_ledger.record_engagement(
            self,
            run_id=run_id,
            target_tweet_id=target_tweet_id,
            target_author=target_author,
            target_tweet_url=target_tweet_url,
            reply_tweet_id=reply_tweet_id,
            reply_url=reply_url,
            followed=followed,
        )

    def record_shared_engagement(
        self,
        *,
        workflow: str,
        run_id: str,
        target_tweet_id: str | None,
        target_author: str | None,
        target_tweet_url: str | None,
        reply_tweet_id: str | None,
        reply_url: str | None,
        followed: bool,
        created_at: str | None = None,
    ) -> None:
        automation_engagement_ledger.record_shared_engagement(
            self,
            workflow=workflow,
            run_id=run_id,
            target_tweet_id=target_tweet_id,
            target_author=target_author,
            target_tweet_url=target_tweet_url,
            reply_tweet_id=reply_tweet_id,
            reply_url=reply_url,
            followed=followed,
            created_at=created_at,
        )

    def list_shared_engagements(self, *, workflow: str | None = None) -> list[dict[str, Any]]:
        return automation_engagement_ledger.list_shared_engagements(self, workflow=workflow)

    def replace_shared_engagements(self, *, workflow: str, rows: list[dict[str, Any]]) -> int:
        return automation_engagement_ledger.replace_shared_engagements(self, workflow=workflow, rows=rows)

    def import_shared_engagements(
        self,
        *,
        workflow: str,
        rows: list[dict[str, Any]],
        replace_existing: bool = False,
    ) -> int:
        return automation_engagement_ledger.import_shared_engagements(
            self,
            workflow=workflow,
            rows=rows,
            replace_existing=replace_existing,
        )

    def delete_shared_engagements(self, *, workflow: str) -> int:
        return automation_engagement_ledger.delete_shared_engagements(self, workflow=workflow)

    def has_target_tweet_id(self, target_tweet_id: str, *, exclude_workflows: tuple[str, ...] | None = None) -> bool:
        return automation_engagement_ledger.has_target_tweet_id(
            self,
            target_tweet_id,
            exclude_workflows=exclude_workflows,
        )

    def get_daily_execution_count(self, workflow: WorkflowKind | str, day: date) -> int:
        normalized = workflow.value if isinstance(workflow, WorkflowKind) else str(workflow)
        normalized = normalized.replace("-", "_")
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM runs
                WHERE job_type = ? AND date(created_at) = ?
                """,
                (normalized, day.isoformat()),
            ).fetchone()
        return int(row["count"]) if row else 0

    def get_global_daily_execution_count(self, metric_date: str) -> int:
        return automation_engagement_ledger.get_global_daily_execution_count(self, metric_date)

    def get_last_author_engagement(self, screen_name: str) -> datetime | None:
        return automation_engagement_ledger.get_last_author_engagement(self, screen_name)
