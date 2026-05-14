from __future__ import annotations

import sqlite3


def initialize_automation_storage_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            config_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
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
            finished_at TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            level TEXT NOT NULL,
            event_type TEXT NOT NULL,
            node TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_runs_job_id ON runs(job_id);
        CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
        CREATE INDEX IF NOT EXISTS idx_audit_events_run_id ON audit_events(run_id);

        CREATE TABLE IF NOT EXISTS dedupe_keys (
            dedupe_key TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS engagements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            target_tweet_id TEXT,
            target_author TEXT,
            target_tweet_url TEXT,
            reply_tweet_id TEXT,
            reply_url TEXT,
            followed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS shared_engagements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow TEXT NOT NULL,
            run_id TEXT NOT NULL,
            target_tweet_id TEXT,
            target_author TEXT,
            target_tweet_url TEXT,
            reply_tweet_id TEXT,
            reply_url TEXT,
            followed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidate_cache (
            workflow TEXT NOT NULL,
            tweet_id TEXT NOT NULL,
            screen_name TEXT,
            created_at TEXT,
            text TEXT,
            metadata_json TEXT,
            status TEXT NOT NULL,
            reason TEXT,
            source_run_id TEXT,
            claim_run_id TEXT,
            claim_expires_at TEXT,
            hydrated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_ts TEXT NOT NULL,
            updated_ts TEXT NOT NULL,
            PRIMARY KEY (workflow, tweet_id)
        );
        """
    )
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(engagements)").fetchall()
    }
    if "target_tweet_url" not in columns:
        connection.execute("ALTER TABLE engagements ADD COLUMN target_tweet_url TEXT")
    if "reply_url" not in columns:
        connection.execute("ALTER TABLE engagements ADD COLUMN reply_url TEXT")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_shared_engagements_target_tweet_id ON shared_engagements(target_tweet_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_shared_engagements_workflow_target ON shared_engagements(workflow, target_tweet_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_shared_engagements_author_created ON shared_engagements(target_author, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_cache_workflow_status_expires ON candidate_cache(workflow, status, expires_at)"
    )
    cache_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(candidate_cache)").fetchall()
    }
    if "claim_run_id" not in cache_columns:
        connection.execute("ALTER TABLE candidate_cache ADD COLUMN claim_run_id TEXT")
    if "claim_expires_at" not in cache_columns:
        connection.execute("ALTER TABLE candidate_cache ADD COLUMN claim_expires_at TEXT")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_cache_source_run_id ON candidate_cache(source_run_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_cache_claim_run_id ON candidate_cache(claim_run_id)"
    )
