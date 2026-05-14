from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from x_atuo.automation.utils import normalize_timestamp, parse_timestamp, utcnow


def list_engagements(storage: Any) -> list[dict[str, Any]]:
    with storage.connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM alpha_engagements
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def record_engagement(
    storage: Any,
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
    normalized_target_author = target_author.strip()
    normalized_target_tweet_id = target_tweet_id.strip()
    normalized_reply_tweet_id = reply_tweet_id.strip()
    if not normalized_target_author or not normalized_target_tweet_id or not normalized_reply_tweet_id:
        raise ValueError("target_author, target_tweet_id, and reply_tweet_id are required")
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO alpha_engagements (
                run_id,
                target_author,
                target_tweet_id,
                target_tweet_url,
                reply_tweet_id,
                reply_url,
                burst_id,
                burst_index,
                burst_size,
                metric_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                normalized_target_author,
                normalized_target_tweet_id,
                target_tweet_url,
                normalized_reply_tweet_id,
                reply_url,
                burst_id.strip() if isinstance(burst_id, str) and burst_id.strip() else None,
                burst_index,
                burst_size,
                metric_date or parse_timestamp(created_at or utcnow()).date().isoformat(),
                normalize_timestamp(created_at or utcnow()),
            ),
        )


def update_burst_size(storage: Any, *, burst_id: str, burst_size: int) -> None:
    normalized_burst_id = burst_id.strip()
    if not normalized_burst_id:
        raise ValueError("burst_id is required")
    with storage.connect() as connection:
        connection.execute(
            """
            UPDATE alpha_engagements
            SET burst_size = ?
            WHERE burst_id = ?
            """,
            (burst_size, normalized_burst_id),
        )


def get_target_success_count(storage: Any, target_tweet_id: str) -> int:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM alpha_engagements
            WHERE target_tweet_id = ?
            """,
            (target_tweet_id,),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_target_last_success_at(storage: Any, target_tweet_id: str) -> str | None:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT created_at
            FROM alpha_engagements
            WHERE target_tweet_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (target_tweet_id,),
        ).fetchone()
    if row is None:
        return None
    value = row["created_at"]
    return str(value) if value is not None else None


def get_author_daily_success_count(storage: Any, target_author: str, *, metric_date: str) -> int:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM alpha_engagements
            WHERE target_author = ? AND metric_date = ?
            """,
            (target_author, metric_date),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_daily_success_count(storage: Any, *, metric_date: str) -> int:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM alpha_engagements
            WHERE metric_date = ?
            """,
            (metric_date,),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_recent_success_count_15m(storage: Any, as_of: str | None = None) -> int:
    anchor = parse_timestamp(as_of or utcnow())
    cutoff = anchor - timedelta(minutes=15)
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM alpha_engagements
            WHERE created_at >= ? AND created_at <= ?
            """,
            (normalize_timestamp(cutoff.isoformat()), normalize_timestamp(anchor.isoformat())),
        ).fetchone()
    return int(row["count"]) if row else 0
