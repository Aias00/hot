from __future__ import annotations

from datetime import date, datetime
from typing import Any

from x_atuo.automation.utils import utcnow


def record_engagement(
    storage: Any,
    *,
    run_id: str,
    target_tweet_id: str | None,
    target_author: str | None,
    target_tweet_url: str | None,
    reply_tweet_id: str | None,
    reply_url: str | None,
    followed: bool,
) -> None:
    created_at = utcnow()
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO engagements (run_id, target_tweet_id, target_author, target_tweet_url, reply_tweet_id, reply_url, followed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, target_tweet_id, target_author, target_tweet_url, reply_tweet_id, reply_url, int(followed), created_at),
        )
    record_shared_engagement(
        storage,
        workflow="feed_engage",
        run_id=run_id,
        target_tweet_id=target_tweet_id,
        target_author=target_author,
        target_tweet_url=target_tweet_url,
        reply_tweet_id=reply_tweet_id,
        reply_url=reply_url,
        followed=followed,
        created_at=created_at,
    )


def record_shared_engagement(
    storage: Any,
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
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO shared_engagements (
                workflow,
                run_id,
                target_tweet_id,
                target_author,
                target_tweet_url,
                reply_tweet_id,
                reply_url,
                followed,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow,
                run_id,
                target_tweet_id,
                target_author,
                target_tweet_url,
                reply_tweet_id,
                reply_url,
                int(followed),
                created_at or utcnow(),
            ),
        )


def list_shared_engagements(storage: Any, *, workflow: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT id, workflow, run_id, target_tweet_id, target_author, target_tweet_url, reply_tweet_id, reply_url, followed, created_at
        FROM shared_engagements
    """
    parameters: tuple[Any, ...] = ()
    if workflow is not None:
        query += " WHERE workflow = ?"
        parameters = (workflow,)
    query += " ORDER BY created_at ASC, id ASC"
    with storage.connect() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def replace_shared_engagements(storage: Any, *, workflow: str, rows: list[dict[str, Any]]) -> int:
    with storage.connect() as connection:
        connection.execute("DELETE FROM shared_engagements WHERE workflow = ?", (workflow,))
        for row in rows:
            connection.execute(
                """
                INSERT INTO shared_engagements (
                    workflow,
                    run_id,
                    target_tweet_id,
                    target_author,
                    target_tweet_url,
                    reply_tweet_id,
                    reply_url,
                    followed,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow,
                    row.get("run_id"),
                    row.get("target_tweet_id"),
                    row.get("target_author"),
                    row.get("target_tweet_url"),
                    row.get("reply_tweet_id"),
                    row.get("reply_url"),
                    int(bool(row.get("followed"))),
                    row.get("created_at") or utcnow(),
                ),
            )
    return len(rows)


def import_shared_engagements(
    storage: Any,
    *,
    workflow: str,
    rows: list[dict[str, Any]],
    replace_existing: bool = False,
) -> int:
    imported_count = 0
    with storage.connect() as connection:
        if replace_existing:
            connection.execute("DELETE FROM shared_engagements WHERE workflow = ?", (workflow,))
        for row in rows:
            run_id = str(row.get("run_id") or "").strip()
            target_tweet_id = row.get("target_tweet_id")
            reply_tweet_id = row.get("reply_tweet_id")
            created_at = row.get("created_at") or utcnow()
            if not run_id:
                raise ValueError("shared_engagements entry must include run_id")
            if not replace_existing:
                existing = connection.execute(
                    """
                    SELECT 1
                    FROM shared_engagements
                    WHERE workflow = ?
                      AND run_id = ?
                      AND ifnull(target_tweet_id, '') = ifnull(?, '')
                      AND ifnull(reply_tweet_id, '') = ifnull(?, '')
                      AND created_at = ?
                    LIMIT 1
                    """,
                    (workflow, run_id, target_tweet_id, reply_tweet_id, created_at),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO shared_engagements (
                    workflow,
                    run_id,
                    target_tweet_id,
                    target_author,
                    target_tweet_url,
                    reply_tweet_id,
                    reply_url,
                    followed,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow,
                    run_id,
                    target_tweet_id,
                    row.get("target_author"),
                    row.get("target_tweet_url"),
                    reply_tweet_id,
                    row.get("reply_url"),
                    int(bool(row.get("followed"))),
                    created_at,
                ),
            )
            imported_count += 1
    return imported_count


def delete_shared_engagements(storage: Any, *, workflow: str) -> int:
    with storage.connect() as connection:
        cursor = connection.execute("DELETE FROM shared_engagements WHERE workflow = ?", (workflow,))
    return int(cursor.rowcount or 0)


def has_target_tweet_id(
    storage: Any,
    target_tweet_id: str,
    *,
    exclude_workflows: tuple[str, ...] | None = None,
) -> bool:
    query = """
            SELECT target_tweet_id
            FROM shared_engagements
            WHERE target_tweet_id = ?
    """
    parameters: list[Any] = [target_tweet_id]
    if exclude_workflows:
        placeholders = ", ".join("?" for _ in exclude_workflows)
        query += f" AND workflow NOT IN ({placeholders})"
        parameters.extend(exclude_workflows)
    query += " LIMIT 1"
    with storage.connect() as connection:
        row = connection.execute(query, tuple(parameters)).fetchone()
    return row is not None


def get_global_daily_execution_count(storage: Any, metric_date: str) -> int:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(DISTINCT NULLIF(reply_tweet_id, '')) AS count
            FROM shared_engagements
            WHERE date(created_at) = ?
            """,
            (metric_date,),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_last_author_engagement(storage: Any, screen_name: str) -> datetime | None:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT created_at
            FROM engagements
            WHERE target_author = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (screen_name,),
        ).fetchone()
    if row is None or not row["created_at"]:
        return None
    return datetime.fromisoformat(row["created_at"])
