from __future__ import annotations

from typing import Any

from x_atuo.automation.utils import utcnow

_UNSET = object()


def record_sync_run(
    storage: Any,
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
    recorded_at = created_at or utcnow()
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO alpha_sync_runs (
                run_id,
                run_type,
                status,
                from_date,
                to_date,
                current_date,
                days_completed,
                days_total,
                resume_from_date,
                error,
                created_at,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_type,
                status,
                from_date,
                to_date,
                current_date,
                days_completed,
                days_total,
                resume_from_date,
                error,
                recorded_at,
                started_at or recorded_at,
                finished_at,
            ),
        )


def update_sync_run(
    storage: Any,
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
    assignments: list[str] = []
    parameters: list[Any] = []
    if status is not _UNSET:
        assignments.append("status = ?")
        parameters.append(status)
    if current_date is not _UNSET:
        assignments.append("current_date = ?")
        parameters.append(current_date)
    if days_completed is not _UNSET:
        assignments.append("days_completed = ?")
        parameters.append(days_completed)
    if days_total is not _UNSET:
        assignments.append("days_total = ?")
        parameters.append(days_total)
    if resume_from_date is not _UNSET:
        assignments.append("resume_from_date = ?")
        parameters.append(resume_from_date)
    if error is not _UNSET:
        assignments.append("error = ?")
        parameters.append(error)
    if started_at is not _UNSET:
        assignments.append("started_at = ?")
        parameters.append(started_at)
    if finished_at is not _UNSET:
        assignments.append("finished_at = ?")
        parameters.append(finished_at)
    if not assignments:
        return
    parameters.append(run_id)
    with storage.connect() as connection:
        connection.execute(
            f"UPDATE alpha_sync_runs SET {', '.join(assignments)} WHERE run_id = ?",
            parameters,
        )


def clear_stale_running_sync_runs(storage: Any, *, reason: str) -> list[str]:
    now = utcnow()
    with storage.connect() as connection:
        rows = connection.execute(
            """
            SELECT run_id
            FROM alpha_sync_runs
            WHERE status = 'running'
            ORDER BY created_at ASC, run_id ASC
            """
        ).fetchall()
        run_ids = [str(row["run_id"]) for row in rows]
        if run_ids:
            placeholders = ", ".join("?" for _ in run_ids)
            connection.execute(
                f"""
                UPDATE alpha_sync_runs
                SET status = 'failed', error = ?, finished_at = ?
                WHERE run_id IN ({placeholders})
                """,
                (reason, now, *run_ids),
            )
    return run_ids


def read_checkpoint(storage: Any, sync_scope: str) -> dict[str, Any] | None:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM alpha_sync_checkpoints
            WHERE sync_scope = ?
            """,
            (sync_scope,),
        ).fetchone()
    return storage._row_to_dict(row)


def write_checkpoint(
    storage: Any,
    *,
    sync_scope: str,
    last_completed_date: str | None,
    next_pending_date: str | None,
    last_run_id: str | None,
    updated_at: str | None = None,
) -> None:
    checkpoint_time = updated_at or utcnow()
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO alpha_sync_checkpoints (
                sync_scope,
                last_completed_date,
                next_pending_date,
                last_run_id,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sync_scope) DO UPDATE SET
                last_completed_date = excluded.last_completed_date,
                next_pending_date = excluded.next_pending_date,
                last_run_id = excluded.last_run_id,
                updated_at = excluded.updated_at
            """,
            (
                sync_scope,
                last_completed_date,
                next_pending_date,
                last_run_id,
                checkpoint_time,
            ),
        )


def get_sync_run(storage: Any, run_id: str) -> dict[str, Any] | None:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM alpha_sync_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    return storage._row_to_dict(row)


def get_active_sync_run(storage: Any) -> dict[str, Any] | None:
    with storage.connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM alpha_sync_runs
            WHERE status = 'running'
            ORDER BY created_at DESC, run_id DESC
            LIMIT 1
            """
        ).fetchone()
    return storage._row_to_dict(row)


def list_sync_runs(storage: Any, *, limit: int | None = 20) -> list[dict[str, Any]]:
    with storage.connect() as connection:
        if limit is None:
            rows = connection.execute(
                """
                SELECT *
                FROM alpha_sync_runs
                ORDER BY created_at DESC, run_id DESC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM alpha_sync_runs
                ORDER BY created_at DESC, run_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]
