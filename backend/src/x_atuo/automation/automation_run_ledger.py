from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from x_atuo.automation.utils import deserialize_json as _deserialize_json
from x_atuo.automation.utils import serialize_json as _serialize_json
from x_atuo.automation.utils import utcnow


def create_run(
    storage: Any,
    *,
    run_id: str,
    job_id: str,
    job_type: str,
    endpoint: str,
    request_payload: dict[str, Any],
    status: str = "queued",
) -> None:
    now = utcnow()
    with storage.connect() as connection:
        connection.execute(
            """
            INSERT INTO runs (
                id, job_id, job_type, endpoint, status, request_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                job_id,
                job_type,
                endpoint,
                status,
                _serialize_json(request_payload) or "{}",
                now,
                now,
            ),
        )


def update_run(
    storage: Any,
    run_id: str,
    *,
    status: str | None = None,
    response_payload: Any = None,
    error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    assignments: list[str] = ["updated_at = ?"]
    parameters: list[Any] = [utcnow()]
    if status is not None:
        assignments.append("status = ?")
        parameters.append(status)
    if response_payload is not None:
        assignments.append("response_json = ?")
        parameters.append(_serialize_json(response_payload))
    if error is not None:
        assignments.append("error = ?")
        parameters.append(error)
    if started_at is not None:
        assignments.append("started_at = ?")
        parameters.append(started_at)
    if finished_at is not None:
        assignments.append("finished_at = ?")
        parameters.append(finished_at)
    parameters.append(run_id)
    with storage.connect() as connection:
        connection.execute(
            f"UPDATE runs SET {', '.join(assignments)} WHERE id = ?",
            parameters,
        )


def add_audit_event(
    storage: Any,
    *,
    run_id: str,
    event_type: str,
    payload: Any = None,
    level: str = "info",
    node: str | None = None,
) -> int:
    with storage.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO audit_events (run_id, level, event_type, node, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, level, event_type, node, _serialize_json(payload), utcnow()),
        )
        return int(cursor.lastrowid)


def get_run(storage: Any, run_id: str) -> dict[str, Any] | None:
    with storage.connect() as connection:
        run_row = connection.execute(
            """
            SELECT id, job_id, job_type, endpoint, status, request_json, response_json,
                   error, created_at, updated_at, started_at, finished_at
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        if run_row is None:
            return None
        audit_rows = connection.execute(
            """
            SELECT id, run_id, level, event_type, node, payload_json, created_at
            FROM audit_events
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()

    return {
        "run": {
            "id": run_row["id"],
            "job_id": run_row["job_id"],
            "job_type": run_row["job_type"],
            "endpoint": run_row["endpoint"],
            "status": run_row["status"],
            "request_payload": _deserialize_json(run_row["request_json"]) or {},
            "response_payload": _deserialize_json(run_row["response_json"]),
            "error": run_row["error"],
            "created_at": run_row["created_at"],
            "updated_at": run_row["updated_at"],
            "started_at": run_row["started_at"],
            "finished_at": run_row["finished_at"],
        },
        "audit_events": [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "level": row["level"],
                "event_type": row["event_type"],
                "node": row["node"],
                "payload": _deserialize_json(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in audit_rows
        ],
    }
