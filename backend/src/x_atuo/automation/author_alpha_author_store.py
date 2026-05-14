from __future__ import annotations

from typing import Any

from x_atuo.automation.utils import utcnow


def upsert_author(
    storage: Any,
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
    now = utcnow()
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO alpha_authors (
                screen_name,
                author_name,
                rest_id,
                author_score,
                reply_count_7d,
                impressions_total_7d,
                avg_impressions_7d,
                max_impressions_7d,
                last_replied_at,
                last_post_seen_at,
                last_scored_at,
                source,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(screen_name) DO UPDATE SET
                author_name = excluded.author_name,
                rest_id = excluded.rest_id,
                author_score = excluded.author_score,
                reply_count_7d = excluded.reply_count_7d,
                impressions_total_7d = excluded.impressions_total_7d,
                avg_impressions_7d = excluded.avg_impressions_7d,
                max_impressions_7d = excluded.max_impressions_7d,
                last_replied_at = excluded.last_replied_at,
                last_post_seen_at = excluded.last_post_seen_at,
                last_scored_at = excluded.last_scored_at,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (
                screen_name,
                author_name,
                rest_id,
                author_score,
                reply_count_7d,
                impressions_total_7d,
                avg_impressions_7d,
                max_impressions_7d,
                last_replied_at,
                last_post_seen_at,
                last_scored_at,
                source,
                now,
                now,
            ),
        )


def list_authors_ordered_by_score(storage: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT *
        FROM alpha_authors
        ORDER BY author_score DESC, avg_impressions_7d DESC, screen_name ASC
    """
    parameters: tuple[Any, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        parameters = (limit,)
    with storage.connect() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def count_authors(storage: Any) -> int:
    with storage.connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM alpha_authors").fetchone()
    return int(row["count"]) if row else 0


def zero_out_stale_authors(storage: Any, scored_screen_names: set[str], *, scored_at: str) -> int:
    parameters: list[Any] = [0.0, 0, 0, 0.0, 0, scored_at, utcnow()]
    where_clause = ""
    if scored_screen_names:
        placeholders = ", ".join("?" for _ in scored_screen_names)
        where_clause = f"WHERE screen_name NOT IN ({placeholders})"
        parameters.extend(sorted(scored_screen_names))
    with storage.connect() as connection:
        cursor = connection.execute(
            f"""
            UPDATE alpha_authors
            SET
                author_score = ?,
                reply_count_7d = ?,
                impressions_total_7d = ?,
                avg_impressions_7d = ?,
                max_impressions_7d = ?,
                last_scored_at = ?,
                updated_at = ?
            {where_clause}
            """,
            parameters,
        )
    return int(cursor.rowcount or 0)
