from __future__ import annotations

import sqlite3


def initialize_author_alpha_storage_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS alpha_authors (
            screen_name TEXT PRIMARY KEY,
            author_name TEXT,
            rest_id TEXT,
            author_score REAL NOT NULL DEFAULT 0,
            reply_count_7d INTEGER NOT NULL DEFAULT 0,
            impressions_total_7d INTEGER NOT NULL DEFAULT 0,
            avg_impressions_7d REAL NOT NULL DEFAULT 0,
            max_impressions_7d INTEGER NOT NULL DEFAULT 0,
            last_replied_at TEXT,
            last_post_seen_at TEXT,
            last_scored_at TEXT,
            source TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alpha_reply_daily_metrics (
            metric_date TEXT NOT NULL,
            reply_tweet_id TEXT NOT NULL,
            target_tweet_id TEXT,
            target_author TEXT,
            impressions INTEGER NOT NULL DEFAULT 0,
            likes INTEGER NOT NULL DEFAULT 0,
            replies INTEGER NOT NULL DEFAULT 0,
            reposts INTEGER NOT NULL DEFAULT 0,
            sampled_at TEXT NOT NULL,
            PRIMARY KEY (metric_date, reply_tweet_id)
        );

        CREATE TABLE IF NOT EXISTS alpha_author_daily_rollups (
            metric_date TEXT NOT NULL,
            target_author TEXT NOT NULL,
            reply_count INTEGER NOT NULL DEFAULT 0,
            impressions_total INTEGER NOT NULL DEFAULT 0,
            likes_total INTEGER NOT NULL DEFAULT 0,
            replies_total INTEGER NOT NULL DEFAULT 0,
            reposts_total INTEGER NOT NULL DEFAULT 0,
            avg_impressions REAL NOT NULL DEFAULT 0,
            max_impressions INTEGER NOT NULL DEFAULT 0,
            computed_at TEXT NOT NULL,
            PRIMARY KEY (metric_date, target_author)
        );

        CREATE TABLE IF NOT EXISTS alpha_sync_runs (
            run_id TEXT PRIMARY KEY,
            run_type TEXT NOT NULL,
            status TEXT NOT NULL,
            from_date TEXT,
            to_date TEXT,
            current_date TEXT,
            days_completed INTEGER NOT NULL DEFAULT 0,
            days_total INTEGER NOT NULL DEFAULT 0,
            resume_from_date TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS alpha_sync_checkpoints (
            sync_scope TEXT PRIMARY KEY,
            last_completed_date TEXT,
            next_pending_date TEXT,
            last_run_id TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alpha_engagements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            target_author TEXT NOT NULL,
            target_tweet_id TEXT NOT NULL,
            target_tweet_url TEXT,
            reply_tweet_id TEXT NOT NULL,
            reply_url TEXT,
            burst_id TEXT,
            burst_index INTEGER,
            burst_size INTEGER,
            metric_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alpha_runs (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            status TEXT NOT NULL,
            request_json TEXT NOT NULL,
            response_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS alpha_run_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            node TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_alpha_authors_score
            ON alpha_authors(author_score DESC, avg_impressions_7d DESC, screen_name ASC);
        CREATE INDEX IF NOT EXISTS idx_alpha_reply_daily_metrics_author
            ON alpha_reply_daily_metrics(metric_date, target_author);
        CREATE INDEX IF NOT EXISTS idx_alpha_author_daily_rollups_author
            ON alpha_author_daily_rollups(metric_date, target_author);
        CREATE INDEX IF NOT EXISTS idx_alpha_engagements_target_tweet
            ON alpha_engagements(target_tweet_id);
        CREATE INDEX IF NOT EXISTS idx_alpha_engagements_author_created
            ON alpha_engagements(target_author, created_at);
        CREATE INDEX IF NOT EXISTS idx_alpha_engagements_created
            ON alpha_engagements(created_at);
        CREATE INDEX IF NOT EXISTS idx_alpha_runs_created
            ON alpha_runs(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_alpha_run_audit_events_run
            ON alpha_run_audit_events(run_id, created_at ASC);
        """
    )
    engagement_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(alpha_engagements)").fetchall()
    }
    if "metric_date" not in engagement_columns:
        connection.execute("ALTER TABLE alpha_engagements ADD COLUMN metric_date TEXT")
        connection.execute(
            """
            UPDATE alpha_engagements
            SET metric_date = substr(created_at, 1, 10)
            WHERE metric_date IS NULL OR metric_date = ''
            """
        )
    if "burst_id" not in engagement_columns:
        connection.execute("ALTER TABLE alpha_engagements ADD COLUMN burst_id TEXT")
    if "burst_index" not in engagement_columns:
        connection.execute("ALTER TABLE alpha_engagements ADD COLUMN burst_index INTEGER")
    if "burst_size" not in engagement_columns:
        connection.execute("ALTER TABLE alpha_engagements ADD COLUMN burst_size INTEGER")
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_alpha_engagements_metric_date
        ON alpha_engagements(metric_date, target_author, created_at)
        """
    )
