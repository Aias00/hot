from __future__ import annotations

from typing import Any


def upsert_reply_daily_metrics(
    storage: Any,
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
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO alpha_reply_daily_metrics (
                metric_date,
                reply_tweet_id,
                target_tweet_id,
                target_author,
                impressions,
                likes,
                replies,
                reposts,
                sampled_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(metric_date, reply_tweet_id) DO UPDATE SET
                target_tweet_id = excluded.target_tweet_id,
                target_author = excluded.target_author,
                impressions = excluded.impressions,
                likes = excluded.likes,
                replies = excluded.replies,
                reposts = excluded.reposts,
                sampled_at = excluded.sampled_at
            """,
            (
                metric_date,
                reply_tweet_id,
                target_tweet_id,
                target_author,
                impressions,
                likes,
                replies,
                reposts,
                sampled_at,
            ),
        )


def upsert_author_daily_rollup(
    storage: Any,
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
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO alpha_author_daily_rollups (
                metric_date,
                target_author,
                reply_count,
                impressions_total,
                likes_total,
                replies_total,
                reposts_total,
                avg_impressions,
                max_impressions,
                computed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(metric_date, target_author) DO UPDATE SET
                reply_count = excluded.reply_count,
                impressions_total = excluded.impressions_total,
                likes_total = excluded.likes_total,
                replies_total = excluded.replies_total,
                reposts_total = excluded.reposts_total,
                avg_impressions = excluded.avg_impressions,
                max_impressions = excluded.max_impressions,
                computed_at = excluded.computed_at
            """,
            (
                metric_date,
                target_author,
                reply_count,
                impressions_total,
                likes_total,
                replies_total,
                reposts_total,
                avg_impressions,
                max_impressions,
                computed_at,
            ),
        )


def replace_day_sync_snapshot(
    storage: Any,
    *,
    metric_date: str,
    reply_metrics: list[dict[str, Any]],
    author_rollups: list[dict[str, Any]],
) -> None:
    with storage.connect() as connection:
        connection.execute("DELETE FROM alpha_reply_daily_metrics WHERE metric_date = ?", (metric_date,))
        connection.execute("DELETE FROM alpha_author_daily_rollups WHERE metric_date = ?", (metric_date,))
        connection.executemany(
            """
            INSERT INTO alpha_reply_daily_metrics (
                metric_date,
                reply_tweet_id,
                target_tweet_id,
                target_author,
                impressions,
                likes,
                replies,
                reposts,
                sampled_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    metric_date,
                    str(row["reply_tweet_id"]),
                    row.get("target_tweet_id"),
                    row.get("target_author"),
                    int(row.get("impressions", 0)),
                    int(row.get("likes", 0)),
                    int(row.get("replies", 0)),
                    int(row.get("reposts", 0)),
                    str(row["sampled_at"]),
                )
                for row in reply_metrics
            ],
        )
        connection.executemany(
            """
            INSERT INTO alpha_author_daily_rollups (
                metric_date,
                target_author,
                reply_count,
                impressions_total,
                likes_total,
                replies_total,
                reposts_total,
                avg_impressions,
                max_impressions,
                computed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    metric_date,
                    str(row["target_author"]),
                    int(row.get("reply_count", 0)),
                    int(row.get("impressions_total", 0)),
                    int(row.get("likes_total", 0)),
                    int(row.get("replies_total", 0)),
                    int(row.get("reposts_total", 0)),
                    float(row.get("avg_impressions", 0.0)),
                    int(row.get("max_impressions", 0)),
                    str(row["computed_at"]),
                )
                for row in author_rollups
            ],
        )


def get_reply_daily_metric(storage: Any, metric_date: str, reply_tweet_id: str) -> dict[str, Any] | None:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM alpha_reply_daily_metrics
            WHERE metric_date = ? AND reply_tweet_id = ?
            """,
            (metric_date, reply_tweet_id),
        ).fetchone()
    return storage._row_to_dict(row)


def get_author_daily_rollup(storage: Any, metric_date: str, target_author: str) -> dict[str, Any] | None:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM alpha_author_daily_rollups
            WHERE metric_date = ? AND target_author = ?
            """,
            (metric_date, target_author),
        ).fetchone()
    return storage._row_to_dict(row)


def list_author_daily_rollups(storage: Any, start_date: str, end_date: str) -> list[dict[str, Any]]:
    with storage.connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM alpha_author_daily_rollups
            WHERE metric_date >= ? AND metric_date <= ?
            ORDER BY metric_date ASC, target_author ASC
            """,
            (start_date, end_date),
        ).fetchall()
    return [dict(row) for row in rows]


def list_reply_daily_metrics(storage: Any, start_date: str, end_date: str) -> list[dict[str, Any]]:
    with storage.connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM alpha_reply_daily_metrics
            WHERE metric_date >= ? AND metric_date <= ?
            ORDER BY metric_date ASC, reply_tweet_id ASC
            """,
            (start_date, end_date),
        ).fetchall()
    return [dict(row) for row in rows]
