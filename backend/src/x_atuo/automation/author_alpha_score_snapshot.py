from __future__ import annotations

from typing import Any

from x_atuo.automation.storage import utcnow
from x_atuo.automation.utils import serialize_json as _serialize_json


def export_score_snapshot(storage: Any) -> dict[str, Any]:
    authors = storage.list_authors_ordered_by_score()
    reply_daily_metrics = storage.list_reply_daily_metrics("0001-01-01", "9999-12-31")
    author_daily_rollups = storage.list_author_daily_rollups("0001-01-01", "9999-12-31")
    sync_runs = storage.list_sync_runs(limit=None)
    sync_checkpoints = storage.list_sync_checkpoints()
    engagements = storage.list_engagements()
    execution_runs = storage.list_execution_runs()
    execution_audit_events = storage.list_execution_audit_events()
    latest_scored_at = max(
        (str(author["last_scored_at"]) for author in authors if author.get("last_scored_at")),
        default=None,
    )
    return {
        "schema_version": 1,
        "exported_at": utcnow(),
        "author_count": len(authors),
        "reply_metric_count": len(reply_daily_metrics),
        "rollup_count": len(author_daily_rollups),
        "sync_run_count": len(sync_runs),
        "sync_checkpoint_count": len(sync_checkpoints),
        "engagement_count": len(engagements),
        "execution_run_count": len(execution_runs),
        "execution_audit_event_count": len(execution_audit_events),
        "latest_scored_at": latest_scored_at,
        "authors": authors,
        "reply_daily_metrics": reply_daily_metrics,
        "author_daily_rollups": author_daily_rollups,
        "sync_runs": sync_runs,
        "sync_checkpoints": sync_checkpoints,
        "engagements": engagements,
        "execution_runs": execution_runs,
        "execution_audit_events": execution_audit_events,
    }


def import_score_snapshot(
    storage: Any,
    snapshot: dict[str, Any],
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    schema_version = int(snapshot.get("schema_version") or 0)
    if schema_version != 1:
        raise ValueError(f"unsupported author-alpha score snapshot schema version: {schema_version}")
    authors = snapshot.get("authors")
    if not isinstance(authors, list):
        raise ValueError("author-alpha score snapshot must include an authors list")
    reply_daily_metrics = snapshot.get("reply_daily_metrics")
    if not isinstance(reply_daily_metrics, list):
        raise ValueError("author-alpha score snapshot must include a reply_daily_metrics list")
    author_daily_rollups = snapshot.get("author_daily_rollups")
    if not isinstance(author_daily_rollups, list):
        raise ValueError("author-alpha score snapshot must include an author_daily_rollups list")
    sync_runs = snapshot.get("sync_runs")
    if not isinstance(sync_runs, list):
        raise ValueError("author-alpha score snapshot must include a sync_runs list")
    sync_checkpoints = snapshot.get("sync_checkpoints")
    if not isinstance(sync_checkpoints, list):
        raise ValueError("author-alpha score snapshot must include a sync_checkpoints list")
    engagements = snapshot.get("engagements")
    if not isinstance(engagements, list):
        raise ValueError("author-alpha score snapshot must include an engagements list")
    execution_runs = snapshot.get("execution_runs")
    if not isinstance(execution_runs, list):
        raise ValueError("author-alpha score snapshot must include an execution_runs list")
    execution_audit_events = snapshot.get("execution_audit_events")
    if not isinstance(execution_audit_events, list):
        raise ValueError("author-alpha score snapshot must include an execution_audit_events list")
    now = utcnow()
    imported_count = 0
    imported_reply_metric_count = 0
    imported_rollup_count = 0
    imported_sync_run_count = 0
    imported_sync_checkpoint_count = 0
    imported_engagement_count = 0
    imported_execution_run_count = 0
    imported_execution_audit_event_count = 0
    with storage.connect() as connection:
        if replace_existing:
            connection.execute("DELETE FROM alpha_authors")
            connection.execute("DELETE FROM alpha_reply_daily_metrics")
            connection.execute("DELETE FROM alpha_author_daily_rollups")
            connection.execute("DELETE FROM alpha_sync_runs")
            connection.execute("DELETE FROM alpha_sync_checkpoints")
            connection.execute("DELETE FROM alpha_engagements")
            connection.execute("DELETE FROM alpha_run_audit_events")
            connection.execute("DELETE FROM alpha_runs")
        for author in authors:
            if not isinstance(author, dict):
                raise ValueError("author-alpha score snapshot authors entries must be objects")
            screen_name = str(author.get("screen_name") or "").strip()
            if not screen_name:
                raise ValueError("author-alpha score snapshot author is missing screen_name")
            created_at = str(author.get("created_at") or now)
            updated_at = str(author.get("updated_at") or now)
            if not replace_existing:
                existing = connection.execute(
                    "SELECT 1 FROM alpha_authors WHERE screen_name = ? LIMIT 1",
                    (screen_name,),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_authors (
                    screen_name, author_name, rest_id, author_score, reply_count_7d,
                    impressions_total_7d, avg_impressions_7d, max_impressions_7d,
                    last_replied_at, last_post_seen_at, last_scored_at, source, created_at, updated_at
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
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    screen_name,
                    author.get("author_name"),
                    author.get("rest_id"),
                    float(author.get("author_score") or 0),
                    int(author.get("reply_count_7d") or 0),
                    int(author.get("impressions_total_7d") or 0),
                    float(author.get("avg_impressions_7d") or 0),
                    int(author.get("max_impressions_7d") or 0),
                    author.get("last_replied_at"),
                    author.get("last_post_seen_at"),
                    author.get("last_scored_at"),
                    author.get("source"),
                    created_at,
                    updated_at,
                ),
            )
            imported_count += 1
        for row in reply_daily_metrics:
            if not isinstance(row, dict):
                raise ValueError("author-alpha score snapshot reply_daily_metrics entries must be objects")
            metric_date = str(row.get("metric_date") or "").strip()
            reply_tweet_id = str(row.get("reply_tweet_id") or "").strip()
            sampled_at = str(row.get("sampled_at") or now)
            if not metric_date or not reply_tweet_id:
                raise ValueError("reply_daily_metrics entry must include metric_date and reply_tweet_id")
            if not replace_existing:
                existing = connection.execute(
                    "SELECT 1 FROM alpha_reply_daily_metrics WHERE metric_date = ? AND reply_tweet_id = ? LIMIT 1",
                    (metric_date, reply_tweet_id),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_reply_daily_metrics (
                    metric_date, reply_tweet_id, target_tweet_id, target_author, impressions,
                    likes, replies, reposts, sampled_at
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
                    row.get("target_tweet_id"),
                    row.get("target_author"),
                    int(row.get("impressions") or 0),
                    int(row.get("likes") or 0),
                    int(row.get("replies") or 0),
                    int(row.get("reposts") or 0),
                    sampled_at,
                ),
            )
            imported_reply_metric_count += 1
        for row in author_daily_rollups:
            if not isinstance(row, dict):
                raise ValueError("author-alpha score snapshot author_daily_rollups entries must be objects")
            metric_date = str(row.get("metric_date") or "").strip()
            target_author = str(row.get("target_author") or "").strip()
            computed_at = str(row.get("computed_at") or now)
            if not metric_date or not target_author:
                raise ValueError("author_daily_rollups entry must include metric_date and target_author")
            if not replace_existing:
                existing = connection.execute(
                    "SELECT 1 FROM alpha_author_daily_rollups WHERE metric_date = ? AND target_author = ? LIMIT 1",
                    (metric_date, target_author),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_author_daily_rollups (
                    metric_date, target_author, reply_count, impressions_total, likes_total,
                    replies_total, reposts_total, avg_impressions, max_impressions, computed_at
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
                    int(row.get("reply_count") or 0),
                    int(row.get("impressions_total") or 0),
                    int(row.get("likes_total") or 0),
                    int(row.get("replies_total") or 0),
                    int(row.get("reposts_total") or 0),
                    float(row.get("avg_impressions") or 0),
                    int(row.get("max_impressions") or 0),
                    computed_at,
                ),
            )
            imported_rollup_count += 1
        for row in sync_runs:
            if not isinstance(row, dict):
                raise ValueError("author-alpha score snapshot sync_runs entries must be objects")
            run_id = str(row.get("run_id") or "").strip()
            run_type = str(row.get("run_type") or "").strip()
            status = str(row.get("status") or "").strip()
            if not run_id or not run_type or not status:
                raise ValueError("sync_runs entry must include run_id, run_type, and status")
            if not replace_existing:
                existing = connection.execute(
                    "SELECT 1 FROM alpha_sync_runs WHERE run_id = ? LIMIT 1",
                    (run_id,),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_sync_runs (
                    run_id, run_type, status, from_date, to_date, current_date,
                    days_completed, days_total, resume_from_date, error, created_at, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    run_type = excluded.run_type,
                    status = excluded.status,
                    from_date = excluded.from_date,
                    to_date = excluded.to_date,
                    current_date = excluded.current_date,
                    days_completed = excluded.days_completed,
                    days_total = excluded.days_total,
                    resume_from_date = excluded.resume_from_date,
                    error = excluded.error,
                    created_at = excluded.created_at,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at
                """,
                (
                    run_id,
                    run_type,
                    status,
                    row.get("from_date"),
                    row.get("to_date"),
                    row.get("current_date"),
                    int(row.get("days_completed") or 0),
                    int(row.get("days_total") or 0),
                    row.get("resume_from_date"),
                    row.get("error"),
                    row.get("created_at") or now,
                    row.get("started_at"),
                    row.get("finished_at"),
                ),
            )
            imported_sync_run_count += 1
        for row in sync_checkpoints:
            if not isinstance(row, dict):
                raise ValueError("author-alpha score snapshot sync_checkpoints entries must be objects")
            sync_scope = str(row.get("sync_scope") or "").strip()
            if not sync_scope:
                raise ValueError("sync_checkpoints entry must include sync_scope")
            if not replace_existing:
                existing = connection.execute(
                    "SELECT 1 FROM alpha_sync_checkpoints WHERE sync_scope = ? LIMIT 1",
                    (sync_scope,),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_sync_checkpoints (
                    sync_scope, last_completed_date, next_pending_date, last_run_id, updated_at
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
                    row.get("last_completed_date"),
                    row.get("next_pending_date"),
                    row.get("last_run_id"),
                    row.get("updated_at") or now,
                ),
            )
            imported_sync_checkpoint_count += 1
        for row in engagements:
            if not isinstance(row, dict):
                raise ValueError("author-alpha score snapshot engagements entries must be objects")
            run_id = str(row.get("run_id") or "").strip()
            target_author = str(row.get("target_author") or "").strip()
            target_tweet_id = str(row.get("target_tweet_id") or "").strip()
            reply_tweet_id = str(row.get("reply_tweet_id") or "").strip()
            if not run_id or not target_author or not target_tweet_id or not reply_tweet_id:
                raise ValueError("engagements entry must include run_id, target_author, target_tweet_id, and reply_tweet_id")
            if not replace_existing:
                existing = connection.execute(
                    "SELECT 1 FROM alpha_engagements WHERE reply_tweet_id = ? LIMIT 1",
                    (reply_tweet_id,),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_engagements (
                    run_id, target_author, target_tweet_id, target_tweet_url, reply_tweet_id, reply_url,
                    burst_id, burst_index, burst_size, metric_date, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    target_author,
                    target_tweet_id,
                    row.get("target_tweet_url"),
                    reply_tweet_id,
                    row.get("reply_url"),
                    row.get("burst_id"),
                    row.get("burst_index"),
                    row.get("burst_size"),
                    row.get("metric_date") or str(row.get("created_at") or "")[:10],
                    row.get("created_at") or now,
                ),
            )
            imported_engagement_count += 1
        for row in execution_runs:
            if not isinstance(row, dict):
                raise ValueError("author-alpha score snapshot execution_runs entries must be objects")
            run_id = str(row.get("id") or "").strip()
            job_id = str(row.get("job_id") or "").strip()
            job_type = str(row.get("job_type") or "").strip()
            endpoint = str(row.get("endpoint") or "").strip()
            status = str(row.get("status") or "").strip()
            if not run_id or not job_id or not job_type or not endpoint or not status:
                raise ValueError("execution_runs entry must include id, job_id, job_type, endpoint, and status")
            if not replace_existing:
                existing = connection.execute(
                    "SELECT 1 FROM alpha_runs WHERE id = ? LIMIT 1",
                    (run_id,),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_runs (
                    id, job_id, job_type, endpoint, status, request_json, response_json, error,
                    created_at, updated_at, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    job_id = excluded.job_id,
                    job_type = excluded.job_type,
                    endpoint = excluded.endpoint,
                    status = excluded.status,
                    request_json = excluded.request_json,
                    response_json = excluded.response_json,
                    error = excluded.error,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at
                """,
                (
                    run_id,
                    job_id,
                    job_type,
                    endpoint,
                    status,
                    _serialize_json(row.get("request_payload")) or "{}",
                    _serialize_json(row.get("response_payload")),
                    row.get("error"),
                    row.get("created_at") or now,
                    row.get("updated_at") or now,
                    row.get("started_at"),
                    row.get("finished_at"),
                ),
            )
            imported_execution_run_count += 1
        for row in execution_audit_events:
            if not isinstance(row, dict):
                raise ValueError("author-alpha score snapshot execution_audit_events entries must be objects")
            run_id = str(row.get("run_id") or "").strip()
            level = str(row.get("level") or "").strip()
            event_type = str(row.get("event_type") or "").strip()
            if not run_id or not level or not event_type:
                raise ValueError("execution_audit_events entry must include run_id, level, and event_type")
            payload_json = _serialize_json(row.get("payload"))
            created_at = row.get("created_at") or now
            if not replace_existing:
                existing = connection.execute(
                    """
                    SELECT 1 FROM alpha_run_audit_events
                    WHERE run_id = ?
                      AND level = ?
                      AND event_type = ?
                      AND ifnull(node, '') = ifnull(?, '')
                      AND ifnull(payload_json, '') = ifnull(?, '')
                      AND created_at = ?
                    LIMIT 1
                    """,
                    (run_id, level, event_type, row.get("node"), payload_json, created_at),
                ).fetchone()
                if existing is not None:
                    continue
            connection.execute(
                """
                INSERT INTO alpha_run_audit_events (
                    run_id, level, event_type, node, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    level,
                    event_type,
                    row.get("node"),
                    payload_json,
                    created_at,
                ),
            )
            imported_execution_audit_event_count += 1
    return {
        "status": "imported",
        "schema_version": schema_version,
        "replace_existing": bool(replace_existing),
        "imported_count": imported_count,
        "imported_reply_metric_count": imported_reply_metric_count,
        "imported_rollup_count": imported_rollup_count,
        "imported_sync_run_count": imported_sync_run_count,
        "imported_sync_checkpoint_count": imported_sync_checkpoint_count,
        "imported_engagement_count": imported_engagement_count,
        "imported_execution_run_count": imported_execution_run_count,
        "imported_execution_audit_event_count": imported_execution_audit_event_count,
        "latest_scored_at": snapshot.get("latest_scored_at"),
    }


