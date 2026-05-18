from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from hot_backend.collectors.models import CollectRequest, CollectWorkflowState, SourceConfig
from hot_backend.text_clean import clean_text_fragment


SCHEMA_VERSION = "1"
REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / ".data" / "aihot.sqlite3"
FEED_SEED_PATH = REPO_ROOT / "public" / "feed-snapshot.json"
DAILY_SEED_PATH = REPO_ROOT / "backend" / "data" / "seed" / "daily_snapshot.json"
MP_SEED_PATH = REPO_ROOT / "backend" / "data" / "seed" / "mp_snapshot.json"
RSS_GENERIC_SAMPLE_PATH = REPO_ROOT / "backend" / "data" / "seed" / "rss_generic_sample.xml"
NAV_HUB_SEED_PATH = REPO_ROOT / "backend" / "data" / "seed" / "nav_hub_seed.json"
DEFAULT_WECHAT_QR_PUBLIC_PATH = REPO_ROOT / "public" / "wechat-qr.png"
DEFAULT_RSS_SOURCE_IDS = (
    "openai-news-rss",
    "github-blog-rss",
    "huggingface-blog-rss",
    "google-developers-blog-rss",
    "google-deepmind-news-rss",
    "google-blog-ai-rss",
    "google-blog-deepmind-rss",
    "google-developers-tech-blog-rss",
    "vercel-news-rss",
    "together-ai-blog-rss",
    "ollama-blog-rss",
    "midjourney-updates-rss",
    "replicate-blog-rss",
    "aws-machine-learning-blog-rss",
    "sambanova-blog-rss",
    "microsoft-foundry-blog-rss",
    "langgraph-blog-rss",
    "kaggle-blog-rss",
    "microsoft-semantic-kernel-blog-rss",
)
REMOVED_DEFAULT_SOURCE_IDS = (
    "mock-hot-source",
    "rss-generic-template",
    "rss-generic-sample",
    "mp-hot-snapshot",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_feed_labels(published_at: str | None, created_at: str | None) -> tuple[str, str]:
    raw = published_at or created_at
    if not raw:
        return ("采集内容", "00:00")
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return (f"{dt.month}月{dt.day}日", dt.strftime("%H:%M"))


def _format_cn_date(issue_date: str) -> str:
    year, month, day = issue_date.split("-")
    return f"{year}年{int(month)}月{int(day)}日"


def _parse_metric_value(value: str | int | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value

    normalized = str(value).strip().lower()
    if normalized == "10w+":
        return 100000

    digits = "".join(ch for ch in normalized if ch.isdigit())
    return int(digits) if digits else 0


def _compute_mp_heat_score(
    reads: str | int | None,
    likes: str | int | None,
    shares: str | int | None,
    outlier: str | int | None,
    ranking_weights: dict[str, Any] | None = None,
) -> int:
    weights = ranking_weights or {}
    reads_divisor = float(weights.get("reads_divisor", 100) or 100)
    likes_multiplier = float(weights.get("likes_multiplier", 2) or 0)
    shares_multiplier = float(weights.get("shares_multiplier", 0.5) or 0)
    outlier_multiplier = float(weights.get("outlier_multiplier", 20) or 0)
    reads_value = _parse_metric_value(reads)
    likes_value = _parse_metric_value(likes)
    shares_value = _parse_metric_value(shares)
    outlier_value = _parse_metric_value(outlier)
    return int(
        reads_value / reads_divisor
        + likes_value * likes_multiplier
        + shares_value * shares_multiplier
        + outlier_value * outlier_multiplier
    )


class HotSQLiteStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            self._create_tables(connection)
            self._ensure_runtime_schema(connection)
            self._ensure_seeded(connection)
            self._ensure_collector_sources(connection)
        # Seed navigation items (outside the connection context to use its own transaction)
        self.seed_navigation_items()
        self.seed_nav_hub_categories()

    def _create_tables(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feed_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              day_label TEXT NOT NULL,
              time_label TEXT NOT NULL,
              source TEXT NOT NULL,
              handle TEXT,
              badge TEXT,
              score TEXT,
              title TEXT,
              body TEXT,
              quoted TEXT,
              reason TEXT,
              tags_json TEXT NOT NULL,
              has_media INTEGER NOT NULL DEFAULT 0,
              link TEXT,
              sort_index INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_issues (
              issue_date TEXT PRIMARY KEY,
              month_label TEXT NOT NULL,
              headline TEXT NOT NULL,
              event_count INTEGER NOT NULL DEFAULT 0,
              volume TEXT NOT NULL,
              issue_title TEXT NOT NULL,
              masthead_date TEXT NOT NULL,
              tagline TEXT NOT NULL,
              is_latest INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS daily_sections (
              issue_date TEXT NOT NULL,
              section_no TEXT NOT NULL,
              title TEXT NOT NULL,
              english TEXT NOT NULL,
              count_label TEXT NOT NULL,
              sort_index INTEGER NOT NULL,
              PRIMARY KEY (issue_date, section_no)
            );

            CREATE TABLE IF NOT EXISTS daily_stories (
              issue_date TEXT NOT NULL,
              section_no TEXT NOT NULL,
              sort_index INTEGER NOT NULL,
              title TEXT NOT NULL,
              href TEXT,
              source_role TEXT,
              source TEXT NOT NULL,
              summary TEXT NOT NULL,
              PRIMARY KEY (issue_date, section_no, sort_index)
            );

            CREATE TABLE IF NOT EXISTS mp_entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              published_date TEXT NOT NULL,
              title TEXT NOT NULL,
              account TEXT NOT NULL,
              href TEXT DEFAULT '',
              account_href TEXT DEFAULT '',
              badge TEXT DEFAULT '',
              reads TEXT NOT NULL,
              likes TEXT NOT NULL,
              shares TEXT NOT NULL,
              outlier TEXT NOT NULL,
              sort_index INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collector_sources (
              source_id TEXT PRIMARY KEY,
              adapter_kind TEXT NOT NULL,
              title TEXT NOT NULL,
              description TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              base_url TEXT,
              seed_urls_json TEXT NOT NULL,
              config_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collector_runs (
              run_id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              status TEXT NOT NULL,
              request_json TEXT NOT NULL,
              summary_json TEXT NOT NULL,
              error TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              started_at TEXT NOT NULL,
              finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS collector_run_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT NOT NULL,
              node TEXT NOT NULL,
              message TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS collector_checkpoints (
              source_id TEXT PRIMARY KEY,
              checkpoint_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hot_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT NOT NULL,
              external_id TEXT NOT NULL,
              canonical_url TEXT NOT NULL,
              title TEXT NOT NULL,
              summary TEXT NOT NULL,
              published_at TEXT,
              author TEXT,
              content_type TEXT NOT NULL,
              tags_json TEXT NOT NULL,
              metrics_json TEXT NOT NULL,
              raw_ref_json TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(source_id, external_id)
            );

            CREATE TABLE IF NOT EXISTS navigation_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              icon TEXT NOT NULL DEFAULT '',
              label TEXT NOT NULL,
              "to" TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS nav_hub_categories (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              icon TEXT NOT NULL,
              color TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS nav_hub_links (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              category_id TEXT NOT NULL,
              title TEXT NOT NULL,
              url TEXT NOT NULL,
              description TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (category_id) REFERENCES nav_hub_categories(id)
            );

            CREATE TABLE IF NOT EXISTS collector_schedule (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              enabled INTEGER NOT NULL DEFAULT 0,
              interval_minutes INTEGER NOT NULL DEFAULT 60,
              last_run_at TEXT,
              next_run_at TEXT,
              last_run_status TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS about_config (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              title TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              qr_code_url TEXT NOT NULL DEFAULT '',
              follow_link TEXT NOT NULL DEFAULT '',
              contact_info TEXT NOT NULL DEFAULT '',
              links_json TEXT NOT NULL DEFAULT '[]',
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    def _ensure_runtime_schema(self, connection: sqlite3.Connection) -> None:
        about_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(about_config)").fetchall()
        }
        if "links_json" not in about_columns:
            connection.execute(
                "ALTER TABLE about_config ADD COLUMN links_json TEXT NOT NULL DEFAULT '[]'"
            )

    def _ensure_seeded(self, connection: sqlite3.Connection) -> None:
        version = connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()

        if version and version["value"] == SCHEMA_VERSION:
            return

        self._seed(connection)

    def _seed(self, connection: sqlite3.Connection) -> None:
        feed_items = _read_json(FEED_SEED_PATH)
        daily_snapshot = _read_json(DAILY_SEED_PATH)
        mp_snapshot = _read_json(MP_SEED_PATH)
        latest_date = (
            daily_snapshot["currentIssueLabel"].split()[-1]
            if daily_snapshot.get("currentIssueLabel")
            else "2026-05-08"
        )

        connection.executescript(
            """
            DELETE FROM meta;
            DELETE FROM feed_items;
            DELETE FROM daily_issues;
            DELETE FROM daily_sections;
            DELETE FROM daily_stories;
            DELETE FROM mp_entries;
            """
        )
        connection.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )

        connection.executemany(
            """
            INSERT INTO feed_items (
              day_label, time_label, source, handle, badge, score, title, body,
              quoted, reason, tags_json, has_media, link, sort_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["day"],
                    item["time"],
                    item["source"],
                    item.get("handle", ""),
                    item.get("badge", ""),
                    item.get("score", ""),
                    item.get("title", ""),
                    item.get("body", ""),
                    item.get("quoted", ""),
                    item.get("reason", ""),
                    json.dumps(item.get("tags", []), ensure_ascii=False),
                    1 if item.get("hasMedia") else 0,
                    item.get("link", ""),
                    index,
                )
                for index, item in enumerate(feed_items)
            ],
        )

        archive_rows: list[tuple[str, str, str, int, str, str, str, str, int]] = []
        for group in daily_snapshot["archiveGroups"]:
            year = int(group["month"].split("年")[0].strip())
            month = int(group["month"].split("年")[1].split("月")[0].strip())
            for issue in group["issues"]:
                day_num = int("".join(ch for ch in issue["day"] if ch.isdigit()))
                issue_date = f"{year:04d}-{month:02d}-{day_num:02d}"
                is_latest = 1 if issue_date == latest_date else 0
                archive_rows.append(
                    (
                        issue_date,
                        f"{year} 年 {month} 月",
                        issue["title"],
                        len(issue["title"]) % 9 + 8,
                        daily_snapshot["masthead"]["volume"]
                        if is_latest
                        else f"VOL. {issue_date.replace('-', '.')} · ISSUE SNAPSHOT · AI DIGEST DAILY",
                        daily_snapshot["masthead"]["title"],
                        daily_snapshot["masthead"]["subtitle"].split(" DAILY")[0]
                        if is_latest
                        else f"{year}年{month}月{day_num}日",
                        "DAILY · 每早八时" if is_latest else "DAILY · 本地快照",
                        is_latest,
                    )
                )

        connection.executemany(
            """
            INSERT INTO daily_issues (
              issue_date, month_label, headline, event_count, volume, issue_title,
              masthead_date, tagline, is_latest
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            archive_rows,
        )

        for section_index, section in enumerate(daily_snapshot["sections"]):
            connection.execute(
                """
                INSERT INTO daily_sections (
                  issue_date, section_no, title, english, count_label, sort_index
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    latest_date,
                    section["number"],
                    section["title"],
                    section["english"],
                    str(len(section["stories"])),
                    section_index,
                ),
            )
            for story_index, story in enumerate(section["stories"]):
                connection.execute(
                    """
                    INSERT INTO daily_stories (
                      issue_date, section_no, sort_index, title, href, source_role, source, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        latest_date,
                        section["number"],
                        story_index,
                        story["title"],
                        story.get("href", ""),
                        "",
                        story["source"],
                        story["summary"],
                    ),
                )

        connection.executemany(
            """
            INSERT INTO mp_entries (
              published_date, title, account, href, account_href, badge,
              reads, likes, shares, outlier, sort_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row[0],
                    row[1],
                    row[2],
                    "",
                    "",
                    "",
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    index,
                )
                for index, row in enumerate(mp_snapshot["rows"])
            ],
        )

        now = datetime.now(timezone.utc).isoformat()
        self._seed_collector_sources(connection, now)

        connection.commit()

    def _seed_collector_sources(self, connection: sqlite3.Connection, now: str | None = None) -> None:
        timestamp = now or datetime.now(timezone.utc).isoformat()
        connection.executemany(
            """
            INSERT INTO collector_sources (
              source_id, adapter_kind, title, description, enabled,
              base_url, seed_urls_json, config_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
              adapter_kind = excluded.adapter_kind,
              title = excluded.title,
              description = excluded.description,
              enabled = excluded.enabled,
              base_url = excluded.base_url,
              seed_urls_json = excluded.seed_urls_json,
              config_json = excluded.config_json,
              updated_at = excluded.updated_at
            """,
            [
                (
                    "openai-news-rss",
                    "rss-generic",
                    "OpenAI News RSS",
                    "OpenAI official news feed.",
                    1,
                    "https://openai.com",
                    json.dumps(["https://openai.com/news/rss.xml"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "github-blog-rss",
                    "rss-generic",
                    "GitHub Blog RSS",
                    "GitHub official blog feed.",
                    1,
                    "https://github.blog",
                    json.dumps(["https://github.blog/feed/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "blog", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "huggingface-blog-rss",
                    "rss-generic",
                    "Hugging Face Blog RSS",
                    "Hugging Face official blog feed.",
                    1,
                    "https://huggingface.co",
                    json.dumps(["https://huggingface.co/blog/feed.xml"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "blog", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "google-developers-blog-rss",
                    "rss-generic",
                    "Google Developers Blog RSS",
                    "Google Developers Blog official feed.",
                    1,
                    "https://developers.googleblog.com",
                    json.dumps(["https://developers.googleblog.com/feeds/posts/default?alt=rss"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "google-deepmind-news-rss",
                    "rss-generic",
                    "Google DeepMind News RSS",
                    "Google DeepMind official news feed.",
                    1,
                    "https://deepmind.google",
                    json.dumps(["https://deepmind.google/blog/rss.xml"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "google-blog-ai-rss",
                    "rss-generic",
                    "Google Blog AI RSS",
                    "Google official AI blog feed.",
                    1,
                    "https://blog.google",
                    json.dumps(["https://blog.google/technology/ai/rss/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "google-blog-deepmind-rss",
                    "rss-generic",
                    "Google Blog DeepMind RSS",
                    "Google official DeepMind blog feed.",
                    1,
                    "https://blog.google",
                    json.dumps(["https://blog.google/technology/google-deepmind/rss/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "google-developers-tech-blog-rss",
                    "rss-generic",
                    "Google Developers Tech Blog RSS",
                    "Google developers tech blog feed with strong AI developer coverage.",
                    1,
                    "https://blog.google",
                    json.dumps(["https://blog.google/technology/developers/rss/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "vercel-news-rss",
                    "rss-generic",
                    "Vercel News RSS",
                    "Vercel official news and product updates feed.",
                    1,
                    "https://vercel.com",
                    json.dumps(["https://vercel.com/atom"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "blog", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "together-ai-blog-rss",
                    "rss-generic",
                    "Together AI Blog RSS",
                    "Together AI official blog feed.",
                    1,
                    "https://www.together.ai",
                    json.dumps(["https://www.together.ai/blog/rss.xml"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "ollama-blog-rss",
                    "rss-generic",
                    "Ollama Blog RSS",
                    "Ollama official blog feed.",
                    1,
                    "https://ollama.com",
                    json.dumps(["https://ollama.com/blog/rss.xml"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "blog", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "midjourney-updates-rss",
                    "rss-generic",
                    "Midjourney Updates RSS",
                    "Midjourney official product updates feed.",
                    1,
                    "https://updates.midjourney.com",
                    json.dumps(["https://updates.midjourney.com/rss/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 30}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "replicate-blog-rss",
                    "rss-generic",
                    "Replicate Blog RSS",
                    "Replicate official blog feed.",
                    1,
                    "https://replicate.com",
                    json.dumps(["https://replicate.com/blog/atom"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "aws-machine-learning-blog-rss",
                    "rss-generic",
                    "AWS Machine Learning Blog RSS",
                    "AWS official machine learning blog feed.",
                    1,
                    "https://aws.amazon.com",
                    json.dumps(["https://aws.amazon.com/blogs/machine-learning/feed/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "sambanova-blog-rss",
                    "rss-generic",
                    "SambaNova Blog RSS",
                    "SambaNova official blog feed.",
                    1,
                    "https://sambanova.ai",
                    json.dumps(["https://sambanova.ai/blog/rss.xml"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "microsoft-foundry-blog-rss",
                    "rss-generic",
                    "Microsoft Foundry Blog RSS",
                    "Microsoft Foundry official developer blog feed.",
                    1,
                    "https://devblogs.microsoft.com",
                    json.dumps(["https://devblogs.microsoft.com/foundry/feed/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "langgraph-blog-rss",
                    "rss-generic",
                    "LangGraph Blog RSS",
                    "LangChain / LangGraph official engineering and product feed.",
                    1,
                    "https://blog.langchain.dev",
                    json.dumps(["https://blog.langchain.dev/rss.xml"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "kaggle-blog-rss",
                    "rss-generic",
                    "Kaggle Blog RSS",
                    "Kaggle official blog feed.",
                    1,
                    "https://medium.com",
                    json.dumps(["https://medium.com/feed/kaggle-blog"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 30}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
                (
                    "microsoft-semantic-kernel-blog-rss",
                    "rss-generic",
                    "Microsoft Semantic Kernel Blog RSS",
                    "Microsoft Semantic Kernel official developer blog feed.",
                    1,
                    "https://devblogs.microsoft.com",
                    json.dumps(["https://devblogs.microsoft.com/semantic-kernel/feed/"], ensure_ascii=False),
                    json.dumps({"timeout_seconds": 20, "category": "official", "freshness_days": 7}, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            ],
        )

    def _prune_removed_default_sources(self, connection: sqlite3.Connection) -> None:
        run_rows = connection.execute(
            f"""
            SELECT run_id
            FROM collector_runs
            WHERE source_id IN ({",".join("?" for _ in REMOVED_DEFAULT_SOURCE_IDS)})
            """,
            REMOVED_DEFAULT_SOURCE_IDS,
        ).fetchall()
        run_ids = [row["run_id"] for row in run_rows]
        if run_ids:
            connection.executemany(
                "DELETE FROM collector_run_events WHERE run_id = ?",
                [(run_id,) for run_id in run_ids],
            )
        connection.execute(
            f"DELETE FROM collector_runs WHERE source_id IN ({','.join('?' for _ in REMOVED_DEFAULT_SOURCE_IDS)})",
            REMOVED_DEFAULT_SOURCE_IDS,
        )
        connection.execute(
            f"DELETE FROM collector_checkpoints WHERE source_id IN ({','.join('?' for _ in REMOVED_DEFAULT_SOURCE_IDS)})",
            REMOVED_DEFAULT_SOURCE_IDS,
        )
        connection.execute(
            f"DELETE FROM hot_items WHERE source_id IN ({','.join('?' for _ in REMOVED_DEFAULT_SOURCE_IDS)})",
            REMOVED_DEFAULT_SOURCE_IDS,
        )
        connection.execute(
            f"DELETE FROM collector_sources WHERE source_id IN ({','.join('?' for _ in REMOVED_DEFAULT_SOURCE_IDS)})",
            REMOVED_DEFAULT_SOURCE_IDS,
        )

    def _prune_orphaned_collector_data(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            DELETE FROM collector_run_events
            WHERE run_id IN (
              SELECT collector_run_events.run_id
              FROM collector_run_events
              LEFT JOIN collector_runs
                ON collector_runs.run_id = collector_run_events.run_id
              WHERE collector_runs.run_id IS NULL
            )
            """
        )
        connection.execute(
            """
            DELETE FROM collector_runs
            WHERE source_id NOT IN (
              SELECT source_id FROM collector_sources
            )
            """
        )
        connection.execute(
            """
            DELETE FROM collector_checkpoints
            WHERE source_id NOT IN (
              SELECT source_id FROM collector_sources
            )
            """
        )
        connection.execute(
            """
            DELETE FROM hot_items
            WHERE source_id NOT IN (
              SELECT source_id FROM collector_sources
            )
            """
        )

    def _ensure_collector_sources(self, connection: sqlite3.Connection) -> None:
        self._seed_collector_sources(connection)
        self._prune_removed_default_sources(connection)
        self._prune_orphaned_collector_data(connection)

    def get_feed_items(
        self,
        *,
        query: str = "",
        page: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            seed_rows = connection.execute(
                """
                SELECT day_label, time_label, source, handle, badge, score, title, body,
                       quoted, reason, tags_json, has_media, link
                FROM feed_items
                ORDER BY sort_index ASC
                """
            ).fetchall()
            hot_rows = connection.execute(
                """
                SELECT hot_items.source_id, hot_items.canonical_url, hot_items.title, hot_items.summary,
                       hot_items.published_at, hot_items.author, hot_items.tags_json,
                       hot_items.metrics_json,
                       hot_items.created_at, collector_sources.title AS source_title,
                       collector_sources.config_json AS source_config_json
                FROM hot_items
                JOIN collector_sources
                  ON collector_sources.source_id = hot_items.source_id
                ORDER BY COALESCE(hot_items.published_at, hot_items.created_at) DESC, hot_items.id DESC
                """
            ).fetchall()

        items = [
            {
                "day": row["day_label"],
                "time": row["time_label"],
                "source": row["source"],
                "sourceId": None,
                "sourceTitle": row["source"],
                "handle": row["handle"],
                "badge": row["badge"],
                "score": row["score"],
                "title": row["title"],
                "body": clean_text_fragment(row["body"]),
                "quoted": row["quoted"],
                "reason": row["reason"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "hasMedia": bool(row["has_media"]),
                "link": row["link"],
                "origin": "seed",
                "publishedAt": None,
            }
            for row in seed_rows
        ]

        collected_items = []
        for row in hot_rows:
            config = json.loads(row["source_config_json"] or "{}")
            metrics = json.loads(row["metrics_json"] or "{}")
            freshness_days = config.get("freshness_days")
            if isinstance(freshness_days, int) and freshness_days > 0 and row["published_at"]:
                published_dt = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
                if published_dt < datetime.now(timezone.utc) - timedelta(days=freshness_days):
                    continue
            day_label, time_label = _to_feed_labels(
                row["published_at"], row["created_at"]
            )
            source_name = row["author"] or row["source_title"] or row["source_id"]
            tags = json.loads(row["tags_json"] or "[]")
            collected_items.append(
                {
                    "day": day_label,
                    "time": time_label,
                    "source": source_name,
                    "sourceId": row["source_id"],
                    "sourceTitle": row["source_title"] or row["source_id"],
                    "handle": "",
                    "badge": "采集",
                    "score": str(metrics.get("hot_score", "")) if metrics.get("hot_score") is not None else "",
                    "title": row["title"],
                    "body": clean_text_fragment(row["summary"]),
                    "quoted": "",
                    "reason": metrics.get("reason") or "由 hot-collect 采集流程导入。",
                    "tags": tags,
                    "hasMedia": False,
                    "link": row["canonical_url"],
                    "origin": "collected",
                    "publishedAt": row["published_at"] or row["created_at"],
                }
            )

        merged_items = collected_items + items
        normalized_query = query.strip().lower()
        if normalized_query:
            merged_items = [
                item
                for item in merged_items
                if normalized_query
                in " ".join(
                    [
                        item.get("source", ""),
                        item.get("sourceTitle", ""),
                        item.get("title", ""),
                        item.get("body", ""),
                        item.get("quoted", ""),
                        item.get("reason", ""),
                        " ".join(item.get("tags", [])),
                    ]
                ).lower()
            ]

        total_count = len(merged_items)
        if page is None or limit is None:
            return {
                "source": "sqlite",
                "count": total_count,
                "total_count": total_count,
                "page": 1,
                "page_size": total_count,
                "has_next": False,
                "items": merged_items,
            }

        current_page = max(1, page)
        offset = (current_page - 1) * limit
        paged_items = merged_items[offset:offset + limit]
        return {
            "source": "sqlite",
            "count": len(paged_items),
            "total_count": total_count,
            "page": current_page,
            "page_size": limit,
            "has_next": offset + len(paged_items) < total_count,
            "items": paged_items,
        }

    def get_collected_items(
        self,
        *,
        query: str = "",
        source_id: str | None = None,
        source_ids: list[str] | None = None,
        tag: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str = "date",
        direction: str = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        normalized_query = query.strip().lower()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT hot_items.source_id, hot_items.external_id, hot_items.canonical_url,
                       hot_items.title, hot_items.summary, hot_items.published_at,
                       hot_items.author, hot_items.tags_json, hot_items.metrics_json, hot_items.created_at,
                       collector_sources.title AS source_title
                FROM hot_items
                JOIN collector_sources
                  ON collector_sources.source_id = hot_items.source_id
                WHERE (? = '' OR lower(hot_items.title || ' ' || hot_items.summary || ' ' || COALESCE(hot_items.author, '')) LIKE '%' || ? || '%')
                  AND (? IS NULL OR hot_items.source_id = ?)
                  AND (? IS NULL OR date(COALESCE(hot_items.published_at, hot_items.created_at)) >= date(?))
                  AND (? IS NULL OR date(COALESCE(hot_items.published_at, hot_items.created_at)) <= date(?))
                ORDER BY hot_items.id DESC
                """,
                (
                    normalized_query,
                    normalized_query,
                    source_id,
                    source_id,
                    from_date,
                    from_date,
                    to_date,
                    to_date,
                ),
            ).fetchall()

        items = []
        for row in rows:
            metrics = json.loads(row["metrics_json"] or "{}")
            item = {
                "source_id": row["source_id"],
                "source_title": row["source_title"] or row["source_id"],
                "external_id": row["external_id"],
                "canonical_url": row["canonical_url"],
                "title": row["title"],
                "summary": clean_text_fragment(row["summary"]),
                "published_at": row["published_at"],
                "author": row["author"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "hot_score": metrics.get("hot_score"),
                "source_category": metrics.get("source_category"),
                "source_category_label": metrics.get("source_category_label"),
                "reason": metrics.get("reason") or "由 hot-collect 采集流程导入。",
                "created_at": row["created_at"],
            }
            items.append(item)

        normalized_source_ids = {
            value.strip()
            for value in (source_ids or [])
            if value and value.strip()
        }
        if normalized_source_ids:
            items = [
                item
                for item in items
                if item["source_id"] in normalized_source_ids
            ]

        if tag:
            items = [item for item in items if tag in item["tags"]]

        def sort_key(item: dict[str, Any]):
            if sort == "source":
                return (item["source_title"] or "").lower()
            if sort == "title":
                return (item["title"] or "").lower()
            return item["published_at"] or item["created_at"] or ""

        reverse = direction != "asc"
        items.sort(key=sort_key, reverse=reverse)

        source_counts: dict[tuple[str, str], int] = {}
        tag_counts: dict[str, int] = {}
        for item in items:
            source_key = (item["source_id"], item["source_title"])
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            for item_tag in item["tags"]:
                tag_counts[item_tag] = tag_counts.get(item_tag, 0) + 1

        total_count = len(items)
        current_page = max(1, page)
        offset = (current_page - 1) * limit
        paged_items = items[offset:offset + limit]

        return {
            "source": "sqlite",
            "count": len(paged_items),
            "total_count": total_count,
            "page": current_page,
            "page_size": limit,
            "has_next": offset + len(paged_items) < total_count,
            "facets": {
                "sources": [
                    {
                        "source_id": source_id_value,
                        "source_title": source_title,
                        "count": count,
                    }
                    for (source_id_value, source_title), count in sorted(
                        source_counts.items(),
                        key=lambda entry: (-entry[1], entry[0][1]),
                    )
                ],
                "tags": [
                    {"tag": tag_name, "count": count}
                    for tag_name, count in sorted(
                        tag_counts.items(),
                        key=lambda entry: (-entry[1], entry[0]),
                    )
                ],
            },
            "items": paged_items,
        }

    def _list_collected_daily_issues(
        self,
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT hot_items.source_id, hot_items.external_id, hot_items.canonical_url,
                   hot_items.title, hot_items.summary, hot_items.published_at,
                   hot_items.author, hot_items.content_type, hot_items.tags_json,
                   hot_items.created_at, collector_sources.title AS source_title,
                   collector_sources.config_json AS source_config_json
            FROM hot_items
            JOIN collector_sources
              ON collector_sources.source_id = hot_items.source_id
            ORDER BY COALESCE(hot_items.published_at, hot_items.created_at) DESC, hot_items.id DESC
            """
        ).fetchall()

        issues: dict[str, dict[str, Any]] = {}
        now = datetime.now(timezone.utc)

        for row in rows:
            raw_published_at = row["published_at"] or row["created_at"]
            if not raw_published_at:
                continue

            published_at = datetime.fromisoformat(raw_published_at.replace("Z", "+00:00"))
            source_config = json.loads(row["source_config_json"] or "{}")
            freshness_days = source_config.get("freshness_days")
            if isinstance(freshness_days, int) and freshness_days > 0:
                if published_at < now - timedelta(days=freshness_days):
                    continue

            issue_date = published_at.date().isoformat()
            issue = issues.setdefault(
                issue_date,
                {
                    "issue_date": issue_date,
                    "month_label": f"{published_at.year} 年 {published_at.month} 月",
                    "headline": row["title"],
                    "event_count": 0,
                    "masthead": {
                        "eyebrow": f"VOL.{issue_date.replace('-', '.')} · COLLECTED HOT ITEMS · AI DIGEST DAILY",
                        "title": "AI Digest 日报",
                        "date": _format_cn_date(issue_date),
                        "tagline": "COLLECTED · hot-collect 采集快报",
                    },
                    "sections_by_source": {},
                },
            )
            issue["event_count"] += 1

            source_title = row["source_title"] or row["source_id"]
            section = issue["sections_by_source"].setdefault(
                source_title,
                {
                    "source_title": source_title,
                    "source_id": row["source_id"],
                    "stories": [],
                },
            )

            author = row["author"]
            source_label = source_title if not author or author == source_title else f"{source_title} · {author}"
            tags = json.loads(row["tags_json"] or "[]")
            section["stories"].append(
                {
                    "title": row["title"],
                    "href": row["canonical_url"],
                    "sourceRole": "采集",
                    "source": source_label,
                    "summary": clean_text_fragment(row["summary"]),
                    "content_type": row["content_type"] or "article",
                    "tags": tags,
                    "published_at": published_at.isoformat(),
                }
            )

        collected_issues: list[dict[str, Any]] = []
        for issue_date, issue in sorted(issues.items(), key=lambda item: item[0], reverse=True):
            sections = []
            source_sections = sorted(
                issue["sections_by_source"].values(),
                key=lambda section: (-len(section["stories"]), section["source_title"].lower()),
            )
            for index, section in enumerate(source_sections, start=1):
                section_stories = sorted(
                    section["stories"],
                    key=lambda story: story["published_at"],
                    reverse=True,
                )
                sections.append(
                    {
                        "number": f"{index:02d}",
                        "title": section["source_title"],
                        "english": "Collected Source",
                        "count": str(len(section_stories)),
                        "stories": [
                            {
                                "title": story["title"],
                                "href": story["href"],
                                "sourceRole": story["sourceRole"],
                                "source": story["source"],
                                "summary": story["summary"],
                            }
                            for story in section_stories
                        ],
                    }
                )

            collected_issues.append(
                {
                    "issue_date": issue_date,
                    "month_label": issue["month_label"],
                    "headline": issue["headline"],
                    "event_count": issue["event_count"],
                    "masthead": issue["masthead"],
                    "sections": sections,
                }
            )

        return collected_issues

    def get_daily_snapshot(self, *, view: str = "issue", date: str = "2026-05-08") -> dict[str, Any]:
        with self.connect() as connection:
            collected_issues = self._list_collected_daily_issues(connection)
            collected_issue_map = {
                issue["issue_date"]: issue for issue in collected_issues
            }
            latest_row = connection.execute(
                "SELECT issue_date FROM daily_issues WHERE is_latest = 1 LIMIT 1"
            ).fetchone()
            latest_date = latest_row["issue_date"] if latest_row else "2026-05-08"
            default_latest_date = collected_issues[0]["issue_date"] if collected_issues else latest_date
            active_date = default_latest_date if date == "2026-05-08" else date
            seed_issue_rows = connection.execute(
                """
                SELECT issue_date, month_label, headline, event_count
                FROM daily_issues
                ORDER BY issue_date DESC
                """
            ).fetchall()
            issue_rows = collected_issues + [
                {
                    "issue_date": row["issue_date"],
                    "month_label": row["month_label"],
                    "headline": row["headline"],
                    "event_count": row["event_count"],
                }
                for row in seed_issue_rows
                if row["issue_date"] not in collected_issue_map
            ]

            sidebar_months: dict[str, list[dict[str, Any]]] = {}
            active_href = (
                "/daily/archive"
                if view == "archive"
                else ("/daily" if active_date == default_latest_date else f"/daily/{active_date}")
            )

            for issue in issue_rows:
                href = (
                    "/daily"
                    if issue["issue_date"] == default_latest_date
                    else f"/daily/{issue['issue_date']}"
                )
                sidebar_months.setdefault(issue["month_label"], []).append(
                    {
                        "day": f"{int(issue['issue_date'][-2:])} 日",
                        "title": issue["headline"],
                        "href": href,
                        "active": href == active_href,
                    }
                )

            sidebar = {
                "latest": {"href": "/daily", "label": "最新一期", "date": default_latest_date},
                "archiveHref": "/daily/archive",
                "months": [
                    {"month": month, "count": str(len(items)), "issues": items}
                    for month, items in sidebar_months.items()
                ],
            }

            if view == "archive":
                return {
                    "mode": "archive",
                    "sidebar": sidebar,
                    "archive": {
                        "title": "AI Digest 日报 · 历史",
                        "subtitle": "DAILY · ARCHIVE",
                        "entries": [
                            {
                                "href": (
                                    "/daily"
                                    if issue["issue_date"] == default_latest_date
                                    else f"/daily/{issue['issue_date']}"
                                ),
                                "date": f"{int(issue['issue_date'][5:7])}月{int(issue['issue_date'][8:10])}日",
                                "headline": issue["headline"],
                                "events": f"{issue['event_count']} 事件",
                            }
                            for issue in issue_rows
                        ],
                    },
                }

            collected_issue = collected_issue_map.get(active_date)
            if collected_issue:
                return {
                    "mode": "issue",
                    "sidebar": sidebar,
                    "masthead": collected_issue["masthead"],
                    "sections": collected_issue["sections"],
                }

            issue = connection.execute(
                """
                SELECT issue_date, headline, volume, issue_title, masthead_date, tagline
                FROM daily_issues
                WHERE issue_date = ?
                LIMIT 1
                """,
                (active_date,),
            ).fetchone()

            sections = connection.execute(
                """
                SELECT section_no, title, english, count_label
                FROM daily_sections
                WHERE issue_date = ?
                ORDER BY sort_index ASC
                """,
                (active_date,),
            ).fetchall()

            if not sections:
                return {
                    "mode": "issue",
                    "sidebar": sidebar,
                    "masthead": {
                        "eyebrow": f"VOL. {active_date.replace('-', '.')} · ISSUE SNAPSHOT · AI DIGEST DAILY",
                        "title": "AI Digest 日报",
                        "date": f"{active_date[:4]}年{int(active_date[5:7])}月{int(active_date[8:10])}日",
                        "tagline": "DAILY · 本地快照",
                    },
                    "sections": [
                        {
                            "number": "01",
                            "title": "当日提要",
                            "english": "Issue Snapshot",
                            "count": "1",
                            "stories": [
                                {
                                    "title": issue["headline"] if issue else "本地快照数据",
                                    "href": active_href,
                                    "sourceRole": "本地",
                                    "source": "SQLite 本地数据接口",
                                    "summary": "当前 SQLite 只保留该日期的标题级摘要，未收录完整正文章节。",
                                }
                            ],
                        }
                    ],
                }

            payload_sections = []
            for section in sections:
                stories = connection.execute(
                    """
                    SELECT title, href, source_role, source, summary
                    FROM daily_stories
                    WHERE issue_date = ? AND section_no = ?
                    ORDER BY sort_index ASC
                    """,
                    (active_date, section["section_no"]),
                ).fetchall()
                payload_sections.append(
                    {
                        "number": section["section_no"],
                        "title": section["title"],
                        "english": section["english"],
                        "count": section["count_label"],
                        "stories": [
                            {
                                "title": story["title"],
                                "href": story["href"],
                                "sourceRole": story["source_role"],
                                "source": story["source"],
                                "summary": clean_text_fragment(story["summary"]),
                            }
                            for story in stories
                        ],
                    }
                )

        return {
            "mode": "issue",
            "sidebar": sidebar,
            "masthead": {
                "eyebrow": issue["volume"],
                "title": issue["issue_title"],
                "date": issue["masthead_date"],
                "tagline": issue["tagline"],
            },
            "sections": payload_sections,
        }

    def get_mp_snapshot(
        self, *, query: str = "", since: str = "30d", page: int = 1
    ) -> dict[str, Any]:
        with self.connect() as connection:
            collected_payload = self._get_collected_mp_snapshot(
                connection,
                query=query,
                since=since,
                page=page,
            )
            if collected_payload is not None:
                return collected_payload

        return self._get_seed_mp_snapshot(query=query, since=since, page=page)

    def _get_collected_mp_snapshot(
        self,
        connection: sqlite3.Connection,
        *,
        query: str,
        since: str,
        page: int,
    ) -> dict[str, Any] | None:
        day_limits = {
            "24h": 1,
            "7d": 7,
            "30d": 30,
            "365d": 365,
            "all": float("inf"),
        }
        normalized_query = query.strip().lower()
        rows = connection.execute(
            """
            SELECT hot_items.title, hot_items.author, hot_items.canonical_url, hot_items.published_at,
                   hot_items.metrics_json, hot_items.raw_ref_json, hot_items.created_at,
                   collector_sources.title AS source_title,
                   collector_sources.config_json AS source_config_json
            FROM hot_items
            JOIN collector_sources
              ON collector_sources.source_id = hot_items.source_id
            WHERE hot_items.content_type = 'mp-article'
            ORDER BY COALESCE(hot_items.published_at, hot_items.created_at) DESC, hot_items.id DESC
            """
        ).fetchall()

        if not rows:
            return None

        items = []
        latest_dt = None
        for row in rows:
            metrics = json.loads(row["metrics_json"] or "{}")
            raw_ref = json.loads(row["raw_ref_json"] or "{}")
            source_config = json.loads(row["source_config_json"] or "{}")
            published_at = row["published_at"] or row["created_at"]
            published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            latest_dt = max(latest_dt, published_dt) if latest_dt else published_dt
            item = {
                "date": published_dt.date().isoformat(),
                "title": row["title"],
                "href": row["canonical_url"],
                "account": row["author"] or row["source_title"] or "公众号来源",
                "accountHref": raw_ref.get("account_href", ""),
                "badge": metrics.get("badge", "采集"),
                "reads": metrics.get("reads", "0"),
                "likes": metrics.get("likes", "0"),
                "shares": metrics.get("shares", "0"),
                "outlier": metrics.get("outlier", "0"),
                "sequence": metrics.get("sequence", 9999),
                "source_mode": raw_ref.get("source_mode", "snapshot-json"),
                "rank_score": _compute_mp_heat_score(
                    metrics.get("reads", "0"),
                    metrics.get("likes", "0"),
                    metrics.get("shares", "0"),
                    metrics.get("outlier", "0"),
                    source_config.get("ranking_weights"),
                ),
                "published_dt": published_dt,
            }
            items.append(item)

        if latest_dt is None:
            return None

        filtered_items = [
            item
            for item in items
            if (
                not normalized_query
                or normalized_query in f"{item['title']} {item['account']}".lower()
            )
        ]
        if since != "all":
            limit_days = day_limits.get(since, 30)
            filtered_items = [
                item
                for item in filtered_items
                if (latest_dt.date() - item["published_dt"].date()).days <= limit_days
            ]

        filtered_items.sort(
            key=lambda item: (
                item["published_dt"],
                item["rank_score"],
                -int(item["sequence"]) if str(item["sequence"]).isdigit() else -9999,
            ),
            reverse=True,
        )

        total_items = len(filtered_items)
        page_size = 10
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        current_page = min(max(1, page), total_pages)
        offset = (current_page - 1) * page_size
        visible_items = filtered_items[offset:offset + page_size]
        mode_set = {item["source_mode"] for item in filtered_items} or {item["source_mode"] for item in items}
        if mode_set == {"html-table"}:
            mode_label = "来源：HTML 榜单解析"
        elif mode_set == {"snapshot-json-home-shell-fallback"}:
            mode_label = "来源：远程路由返回首页壳，回退本地快照"
        elif mode_set == {"snapshot-json-fallback"}:
            mode_label = "来源：远程页不可用，回退本地快照"
        else:
            mode_label = "来源：本地快照回退"

        return {
            "source": "collector",
            "title": "公众号爆文",
            "subtitle": f"AI 领域低粉爆款选题池 · 当前筛选 {total_items} 条",
            "pagerLabel": f"P {current_page}",
            "pageMeta": ["状态：采集读模型", mode_label, "排序：热度排序", f"最新日期：{latest_dt.date().isoformat()}"],
            "filters": {
                "query": query,
                "since": since,
                "options": [
                    {"label": "过去 24h", "value": "24h"},
                    {"label": "过去 7 天", "value": "7d"},
                    {"label": "过去 30 天", "value": "30d"},
                    {"label": "过去 1 年", "value": "365d"},
                    {"label": "全部", "value": "all"},
                ],
            },
            "pagination": {
                "currentPage": current_page,
                "pages": [
                    {"label": str(number), "page": number, "current": number == current_page}
                    for number in range(1, total_pages + 1)
                ],
                "prevPage": max(1, current_page - 1),
                "nextPage": min(total_pages, current_page + 1),
                "hasPrev": current_page > 1,
                "hasNext": current_page < total_pages,
                "pageSize": page_size,
                "totalItems": total_items,
            },
            "rows": [
                {
                    "date": item["date"],
                    "title": item["title"],
                    "href": item["href"],
                    "account": item["account"],
                    "accountHref": item["accountHref"],
                    "badge": item["badge"],
                    "reads": item["reads"],
                    "likes": item["likes"],
                    "shares": item["shares"],
                    "outlier": item["outlier"],
                }
                for item in visible_items
            ],
        }

    def _get_seed_mp_snapshot(
        self, *, query: str = "", since: str = "30d", page: int = 1
    ) -> dict[str, Any]:
        day_limits = {
            "24h": 1,
            "7d": 7,
            "30d": 30,
            "365d": 365,
            "all": float("inf"),
        }

        normalized_query = query.strip().lower()

        with self.connect() as connection:
            latest_date = connection.execute(
                "SELECT MAX(published_date) AS latest FROM mp_entries"
            ).fetchone()["latest"]

            where_sql = """
                WHERE (? = '' OR lower(title || ' ' || account) LIKE '%' || ? || '%')
                  AND (? = 'all' OR (julianday(?) - julianday(published_date)) <= ?)
            """
            params = (
                normalized_query,
                normalized_query,
                since,
                latest_date,
                day_limits.get(since, 30),
            )

            total_items = connection.execute(
                f"SELECT COUNT(*) AS total FROM mp_entries {where_sql}",
                params,
            ).fetchone()["total"]
            page_size = 10
            total_pages = max(1, (total_items + page_size - 1) // page_size)
            current_page = min(max(1, page), total_pages)
            offset = (current_page - 1) * page_size

            rows = connection.execute(
                f"""
                SELECT published_date, title, account, href, account_href, badge,
                       reads, likes, shares, outlier
                FROM mp_entries
                {where_sql}
                ORDER BY published_date DESC, sort_index ASC
                LIMIT ? OFFSET ?
                """,
                (*params, page_size, offset),
            ).fetchall()

        return {
            "source": "sqlite",
            "title": "公众号爆文",
            "subtitle": f"AI 领域低粉爆款选题池 · 当前筛选 {total_items} 条",
            "pagerLabel": f"P {current_page}",
            "pageMeta": ["状态：正常", "上次抓取：05-07 15:09", "下次：5 小时后"],
            "filters": {
                "query": query,
                "since": since,
                "options": [
                    {"label": "过去 24h", "value": "24h"},
                    {"label": "过去 7 天", "value": "7d"},
                    {"label": "过去 30 天", "value": "30d"},
                    {"label": "过去 1 年", "value": "365d"},
                    {"label": "全部", "value": "all"},
                ],
            },
            "pagination": {
                "currentPage": current_page,
                "pages": [
                    {
                        "label": str(number),
                        "page": number,
                        "current": number == current_page,
                    }
                    for number in range(1, total_pages + 1)
                ],
                "prevPage": max(1, current_page - 1),
                "nextPage": min(total_pages, current_page + 1),
                "hasPrev": current_page > 1,
                "hasNext": current_page < total_pages,
                "pageSize": page_size,
                "totalItems": total_items,
            },
            "rows": [
                {
                    "date": row["published_date"],
                    "title": row["title"],
                    "href": row["href"],
                    "account": row["account"],
                    "accountHref": row["account_href"],
                    "badge": row["badge"],
                    "reads": row["reads"],
                    "likes": row["likes"],
                    "shares": row["shares"],
                    "outlier": row["outlier"],
                }
                for row in rows
            ],
        }

    def list_collector_sources(self) -> list[SourceConfig]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT source_id, adapter_kind, title, description, enabled, base_url,
                       seed_urls_json, config_json
                FROM collector_sources
                ORDER BY enabled DESC, source_id ASC
                """
            ).fetchall()

        return [
            SourceConfig(
                source_id=row["source_id"],
                adapter_kind=row["adapter_kind"],
                title=row["title"],
                description=row["description"],
                enabled=bool(row["enabled"]),
                base_url=row["base_url"],
                seed_urls=json.loads(row["seed_urls_json"] or "[]"),
                config_json=json.loads(row["config_json"] or "{}"),
            )
            for row in rows
        ]

    def get_collector_source(self, source_id: str) -> SourceConfig:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT source_id, adapter_kind, title, description, enabled, base_url,
                       seed_urls_json, config_json
                FROM collector_sources
                WHERE source_id = ?
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"collector source not found: {source_id}")

        return SourceConfig(
            source_id=row["source_id"],
            adapter_kind=row["adapter_kind"],
            title=row["title"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            base_url=row["base_url"],
            seed_urls=json.loads(row["seed_urls_json"] or "[]"),
            config_json=json.loads(row["config_json"] or "{}"),
        )

    def upsert_collector_source(self, source: SourceConfig) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO collector_sources (
                  source_id, adapter_kind, title, description, enabled,
                  base_url, seed_urls_json, config_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                  adapter_kind = excluded.adapter_kind,
                  title = excluded.title,
                  description = excluded.description,
                  enabled = excluded.enabled,
                  base_url = excluded.base_url,
                  seed_urls_json = excluded.seed_urls_json,
                  config_json = excluded.config_json,
                  updated_at = excluded.updated_at
                """,
                (
                    source.source_id,
                    source.adapter_kind,
                    source.title,
                    source.description,
                    1 if source.enabled else 0,
                    source.base_url,
                    json.dumps(source.seed_urls, ensure_ascii=False),
                    json.dumps(source.config_json, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def delete_collector_source(self, source_id: str) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM collector_sources WHERE source_id = ?",
                (source_id,),
            )
        if (cursor.rowcount or 0) == 0:
            raise KeyError(f"collector source not found: {source_id}")

    def get_collector_checkpoint(self, source_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT checkpoint_json
                FROM collector_checkpoints
                WHERE source_id = ?
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()

        return json.loads(row["checkpoint_json"]) if row else {}

    def upsert_collector_checkpoint(self, source_id: str, checkpoint: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO collector_checkpoints (source_id, checkpoint_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                  checkpoint_json = excluded.checkpoint_json,
                  updated_at = excluded.updated_at
                """,
                (source_id, json.dumps(checkpoint, ensure_ascii=False), now),
            )

    def create_collector_run(self, run_id: str, request: CollectRequest) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO collector_runs (
                  run_id, source_id, status, request_json, summary_json,
                  error, created_at, updated_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL)
                """,
                (
                    run_id,
                    request.source_id,
                    "running",
                    request.model_dump_json(),
                    json.dumps({}, ensure_ascii=False),
                    now,
                    now,
                    now,
                ),
            )

    def complete_collector_run(self, snapshot: CollectWorkflowState) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE collector_runs
                SET status = ?, summary_json = ?, updated_at = ?, finished_at = ?, error = ?
                WHERE run_id = ?
                """,
                (
                    snapshot.status,
                    snapshot.summary.model_dump_json(),
                    now,
                    now,
                    "\n".join(snapshot.errors) if snapshot.errors else None,
                    snapshot.run_id,
                ),
            )
            connection.executemany(
                """
                INSERT INTO collector_run_events (
                  run_id, node, message, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot.run_id,
                        event.node,
                        event.message,
                        json.dumps(event.payload, ensure_ascii=False),
                        event.created_at.isoformat(),
                    )
                    for event in snapshot.events
                ],
            )

    def get_collector_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            run = connection.execute(
                """
                SELECT run_id, source_id, status, request_json, summary_json,
                       error, created_at, updated_at, started_at, finished_at
                FROM collector_runs
                WHERE run_id = ?
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if run is None:
                return None
            events = connection.execute(
                """
                SELECT node, message, payload_json, created_at
                FROM collector_run_events
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()

        return {
            "run": {
                "run_id": run["run_id"],
                "source_id": run["source_id"],
                "status": run["status"],
                "request": json.loads(run["request_json"]),
                "summary": json.loads(run["summary_json"]),
                "error": run["error"],
                "created_at": run["created_at"],
                "updated_at": run["updated_at"],
                "started_at": run["started_at"],
                "finished_at": run["finished_at"],
            },
            "events": [
                {
                    "node": event["node"],
                    "message": event["message"],
                    "payload": json.loads(event["payload_json"]),
                    "created_at": event["created_at"],
                }
                for event in events
            ],
        }

    def list_collector_runs(
        self,
        *,
        limit: int = 20,
        source_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if source_id:
                rows = connection.execute(
                    """
                    SELECT collector_runs.run_id, collector_runs.source_id, collector_runs.status, collector_runs.request_json, collector_runs.summary_json,
                           collector_runs.error,
                           collector_runs.created_at,
                           collector_runs.updated_at,
                           collector_runs.started_at,
                           collector_runs.finished_at
                    FROM collector_runs
                    JOIN collector_sources
                      ON collector_sources.source_id = collector_runs.source_id
                    WHERE collector_runs.source_id = ?
                      AND collector_sources.adapter_kind = 'rss-generic'
                    ORDER BY collector_runs.created_at DESC
                    LIMIT ?
                    """,
                    (source_id, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT collector_runs.run_id, collector_runs.source_id, collector_runs.status, collector_runs.request_json, collector_runs.summary_json,
                           collector_runs.error,
                           collector_runs.created_at,
                           collector_runs.updated_at,
                           collector_runs.started_at,
                           collector_runs.finished_at
                    FROM collector_runs
                    JOIN collector_sources
                      ON collector_sources.source_id = collector_runs.source_id
                    WHERE collector_sources.adapter_kind = 'rss-generic'
                    ORDER BY collector_runs.created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [
            {
                "run_id": row["run_id"],
                "source_id": row["source_id"],
                "status": row["status"],
                "request": json.loads(row["request_json"]),
                "summary": json.loads(row["summary_json"]),
                "error": row["error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
            for row in rows
        ]

    def persist_hot_items(self, items: list[Any]) -> int:
        if not items:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            for item in items:
                connection.execute(
                    """
                    INSERT INTO hot_items (
                      source_id, external_id, canonical_url, title, summary, published_at,
                      author, content_type, tags_json, metrics_json, raw_ref_json,
                      content_hash, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id, external_id) DO UPDATE SET
                      canonical_url = excluded.canonical_url,
                      title = excluded.title,
                      summary = excluded.summary,
                      published_at = excluded.published_at,
                      author = excluded.author,
                      content_type = excluded.content_type,
                      tags_json = excluded.tags_json,
                      metrics_json = excluded.metrics_json,
                      raw_ref_json = excluded.raw_ref_json,
                      content_hash = excluded.content_hash,
                      updated_at = excluded.updated_at
                    """,
                    (
                        item.source_id,
                        item.external_id,
                        item.canonical_url,
                        item.title,
                        item.summary,
                        item.published_at.isoformat() if item.published_at else None,
                        item.author,
                        item.content_type,
                        json.dumps(item.tags, ensure_ascii=False),
                        json.dumps(item.metrics, ensure_ascii=False),
                        json.dumps(item.raw_ref, ensure_ascii=False),
                        item.content_hash,
                        now,
                        now,
                    ),
                )

        return len(items)

    # ==================== Admin: Sources Management ====================

    def list_sources(self) -> list[dict]:
        """List all collector sources as dictionaries."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source_id, adapter_kind, title, description, enabled, base_url, seed_urls_json, config_json, created_at, updated_at FROM collector_sources ORDER BY title"
            ).fetchall()
            return [
                {
                    "source_id": row[0],
                    "adapter_kind": row[1],
                    "title": row[2],
                    "description": row[3],
                    "enabled": bool(row[4]),
                    "base_url": row[5],
                    "seed_urls": json.loads(row[6]) if row[6] else [],
                    "config": json.loads(row[7]) if row[7] else {},
                    "created_at": row[8],
                    "updated_at": row[9],
                }
                for row in rows
            ]

    def get_source(self, source_id: str) -> dict | None:
        """Get a single source by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT source_id, adapter_kind, title, description, enabled, base_url, seed_urls_json, config_json, created_at, updated_at FROM collector_sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "source_id": row[0],
                "adapter_kind": row[1],
                "title": row[2],
                "description": row[3],
                "enabled": bool(row[4]),
                "base_url": row[5],
                "seed_urls": json.loads(row[6]) if row[6] else [],
                "config": json.loads(row[7]) if row[7] else {},
                "created_at": row[8],
                "updated_at": row[9],
            }

    def create_source(self, source: dict) -> dict:
        """Create a new source."""
        now = datetime.now(timezone.utc).isoformat()
        source_id = source.get("source_id")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO collector_sources (source_id, adapter_kind, title, description, enabled, base_url, seed_urls_json, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source.get("adapter_kind", "rss-generic"),
                    source.get("title", ""),
                    source.get("description", ""),
                    1 if source.get("enabled", True) else 0,
                    source.get("base_url"),
                    json.dumps(source.get("seed_urls", []), ensure_ascii=False),
                    json.dumps(source.get("config", {}), ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get_source(source_id)  # type: ignore

    def update_source(self, source_id: str, updates: dict) -> dict:
        """Update an existing source."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_source(source_id)
        if not existing:
            raise ValueError(f"Source '{source_id}' not found")

        # Build update query dynamically
        fields = []
        values = []
        if "title" in updates:
            fields.append("title = ?")
            values.append(updates["title"])
        if "description" in updates:
            fields.append("description = ?")
            values.append(updates["description"])
        if "enabled" in updates:
            fields.append("enabled = ?")
            values.append(1 if updates["enabled"] else 0)
        if "base_url" in updates:
            fields.append("base_url = ?")
            values.append(updates["base_url"])
        if "seed_urls" in updates:
            fields.append("seed_urls_json = ?")
            values.append(json.dumps(updates["seed_urls"], ensure_ascii=False))
        if "config" in updates:
            fields.append("config_json = ?")
            values.append(json.dumps(updates["config"], ensure_ascii=False))
        if "adapter_kind" in updates:
            fields.append("adapter_kind = ?")
            values.append(updates["adapter_kind"])

        if fields:
            fields.append("updated_at = ?")
            values.append(now)
            values.append(source_id)
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE collector_sources SET {', '.join(fields)} WHERE source_id = ?",
                    values,
                )
        return self.get_source(source_id)  # type: ignore

    def delete_source(self, source_id: str) -> None:
        """Delete a source and its related data."""
        with self.connect() as conn:
            conn.execute("DELETE FROM collector_checkpoints WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM collector_runs WHERE source_id = ?", (source_id,))
            conn.execute("DELETE FROM collector_sources WHERE source_id = ?", (source_id,))

    # ==================== Admin: Navigation Management ====================

    def list_navigation_items(self) -> list[dict]:
        """List all navigation items, sorted by sort_order."""
        with self.connect() as conn:
            rows = conn.execute(
                'SELECT id, icon, label, "to", sort_order, enabled, created_at, updated_at FROM navigation_items ORDER BY sort_order'
            ).fetchall()
            return [
                {
                    "id": row[0],
                    "icon": row[1],
                    "label": row[2],
                    "to": row[3],
                    "sort_order": row[4],
                    "enabled": bool(row[5]),
                    "created_at": row[6],
                    "updated_at": row[7],
                }
                for row in rows
            ]

    def get_navigation_item(self, item_id: int) -> dict | None:
        """Get a single navigation item by ID."""
        with self.connect() as conn:
            row = conn.execute(
                'SELECT id, icon, label, "to", sort_order, enabled, created_at, updated_at FROM navigation_items WHERE id = ?',
                (item_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "icon": row[1],
                "label": row[2],
                "to": row[3],
                "sort_order": row[4],
                "enabled": bool(row[5]),
                "created_at": row[6],
                "updated_at": row[7],
            }

    def create_navigation_item(self, item: dict) -> dict:
        """Create a new navigation item."""
        now = datetime.now(timezone.utc).isoformat()
        # Get max sort_order
        with self.connect() as conn:
            max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM navigation_items").fetchone()[0]
            sort_order = item.get("sort_order", max_order + 1)
            cursor = conn.execute(
                """
                INSERT INTO navigation_items (icon, label, "to", sort_order, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("icon", ""),
                    item.get("label", ""),
                    item.get("to", ""),
                    sort_order,
                    1 if item.get("enabled", True) else 0,
                    now,
                    now,
                ),
            )
            item_id = cursor.lastrowid
        return self.get_navigation_item(item_id)  # type: ignore

    def update_navigation_item(self, item_id: int, updates: dict) -> dict:
        """Update an existing navigation item."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_navigation_item(item_id)
        if not existing:
            raise ValueError(f"Navigation item '{item_id}' not found")

        fields = []
        values = []
        if "icon" in updates:
            fields.append("icon = ?")
            values.append(updates["icon"])
        if "label" in updates:
            fields.append("label = ?")
            values.append(updates["label"])
        if "to" in updates:
            fields.append("to = ?")
            values.append(updates["to"])
        if "sort_order" in updates:
            fields.append("sort_order = ?")
            values.append(updates["sort_order"])
        if "enabled" in updates:
            fields.append("enabled = ?")
            values.append(1 if updates["enabled"] else 0)

        if fields:
            fields.append("updated_at = ?")
            values.append(now)
            values.append(item_id)
            with self.connect() as conn:
                conn.execute(
                    f"UPDATE navigation_items SET {', '.join(fields)} WHERE id = ?",
                    values,
                )
        return self.get_navigation_item(item_id)  # type: ignore

    def delete_navigation_item(self, item_id: int) -> None:
        """Delete a navigation item."""
        with self.connect() as conn:
            conn.execute("DELETE FROM navigation_items WHERE id = ?", (item_id,))

    def seed_navigation_items(self) -> None:
        """Seed default navigation items and backfill missing defaults."""
        now = datetime.now(timezone.utc).isoformat()
        default_items = [
            {"icon": "◫", "label": "导航中心", "to": "/nav-hub", "sort_order": 0},
            {"icon": "☰", "label": "全部 AI 动态", "to": "/all", "sort_order": 1},
            {"icon": "◉", "label": "关于", "to": "/about", "sort_order": 2},
        ]
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM navigation_items").fetchone()[0]
            max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM navigation_items").fetchone()[0]
            for item in default_items:
                existing = conn.execute(
                    'SELECT id FROM navigation_items WHERE "to" = ?',
                    (item["to"],),
                ).fetchone()
                if existing:
                    continue

                sort_order = item["sort_order"] if count == 0 else max_order + 1
                conn.execute(
                    """
                    INSERT INTO navigation_items (icon, label, "to", sort_order, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (item["icon"], item["label"], item["to"], sort_order, 1, now, now),
                )
                count += 1
                max_order = sort_order

    def seed_nav_hub_categories(self) -> None:
        """Seed default nav hub categories and links if tables are empty."""
        seed_categories = _read_json(NAV_HUB_SEED_PATH)
        now = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:
            category_count = conn.execute("SELECT COUNT(*) FROM nav_hub_categories").fetchone()[0]
            link_count = conn.execute("SELECT COUNT(*) FROM nav_hub_links").fetchone()[0]
            if category_count > 0 or link_count > 0:
                return

            for category_index, category in enumerate(seed_categories):
                conn.execute(
                    """
                    INSERT INTO nav_hub_categories (id, name, icon, color, sort_order, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        category["id"],
                        category["name"],
                        category.get("icon", ""),
                        category.get("color", "#7dd3fc"),
                        category_index,
                        1,
                        now,
                        now,
                    ),
                )

                for link_index, link in enumerate(category.get("links", [])):
                    conn.execute(
                        """
                        INSERT INTO nav_hub_links (category_id, title, url, description, sort_order, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            category["id"],
                            link["title"],
                            link["url"],
                            link.get("description", ""),
                            link_index,
                            1,
                            now,
                            now,
                        ),
                    )

    # ==================== Nav Hub Categories ====================

    def list_nav_hub_categories(self) -> list[dict]:
        """List all nav hub categories with their links."""
        with self.connect() as conn:
            cat_rows = conn.execute(
                "SELECT id, name, icon, color, sort_order, enabled, created_at, updated_at FROM nav_hub_categories ORDER BY sort_order"
            ).fetchall()
            categories = []
            for row in cat_rows:
                cat = {
                    "id": row[0],
                    "name": row[1],
                    "icon": row[2],
                    "color": row[3],
                    "sort_order": row[4],
                    "enabled": bool(row[5]),
                    "created_at": row[6],
                    "updated_at": row[7],
                    "links": [],
                }
                link_rows = conn.execute(
                    "SELECT id, title, url, description, sort_order, enabled FROM nav_hub_links WHERE category_id = ? ORDER BY sort_order",
                    (row[0],),
                ).fetchall()
                cat["links"] = [
                    {
                        "id": link[0],
                        "title": link[1],
                        "url": link[2],
                        "description": link[3],
                        "sort_order": link[4],
                        "enabled": bool(link[5]),
                    }
                    for link in link_rows
                ]
                categories.append(cat)
            return categories

    def get_nav_hub_category(self, category_id: str) -> dict | None:
        """Get a single nav hub category by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, name, icon, color, sort_order, enabled, created_at, updated_at FROM nav_hub_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "name": row[1],
                "icon": row[2],
                "color": row[3],
                "sort_order": row[4],
                "enabled": bool(row[5]),
                "created_at": row[6],
                "updated_at": row[7],
            }

    def create_nav_hub_category(self, category: dict) -> dict:
        """Create a new nav hub category."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM nav_hub_categories").fetchone()[0]
            conn.execute(
                """
                INSERT INTO nav_hub_categories (id, name, icon, color, sort_order, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category["id"],
                    category["name"],
                    category.get("icon", ""),
                    category.get("color", "#7dd3fc"),
                    category.get("sort_order", max_order + 1),
                    1 if category.get("enabled", True) else 0,
                    now,
                    now,
                ),
            )
        return self.get_nav_hub_category(category["id"])  # type: ignore

    def update_nav_hub_category(self, category_id: str, updates: dict) -> dict:
        """Update a nav hub category."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_nav_hub_category(category_id)
        if not existing:
            raise ValueError(f"Category '{category_id}' not found")

        fields = []
        values = []
        for field in ["name", "icon", "color", "sort_order", "enabled"]:
            if field in updates:
                fields.append(f"{field} = ?")
                values.append(updates[field] if field != "enabled" else (1 if updates[field] else 0))

        if fields:
            fields.append("updated_at = ?")
            values.append(now)
            values.append(category_id)
            with self.connect() as conn:
                conn.execute(f"UPDATE nav_hub_categories SET {', '.join(fields)} WHERE id = ?", values)
        return self.get_nav_hub_category(category_id)  # type: ignore

    def delete_nav_hub_category(self, category_id: str) -> None:
        """Delete a nav hub category and all its links."""
        with self.connect() as conn:
            conn.execute("DELETE FROM nav_hub_links WHERE category_id = ?", (category_id,))
            conn.execute("DELETE FROM nav_hub_categories WHERE id = ?", (category_id,))

    # ==================== Nav Hub Links ====================

    def get_nav_hub_link(self, link_id: int) -> dict | None:
        """Get a single nav hub link by ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, category_id, title, url, description, sort_order, enabled, created_at, updated_at FROM nav_hub_links WHERE id = ?",
                (link_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "category_id": row[1],
                "title": row[2],
                "url": row[3],
                "description": row[4],
                "sort_order": row[5],
                "enabled": bool(row[6]),
                "created_at": row[7],
                "updated_at": row[8],
            }

    def create_nav_hub_link(self, link: dict) -> dict:
        """Create a new nav hub link."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM nav_hub_links WHERE category_id = ?",
                (link["category_id"],),
            ).fetchone()[0]
            cursor = conn.execute(
                """
                INSERT INTO nav_hub_links (category_id, title, url, description, sort_order, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link["category_id"],
                    link["title"],
                    link["url"],
                    link.get("description", ""),
                    link.get("sort_order", max_order + 1),
                    1 if link.get("enabled", True) else 0,
                    now,
                    now,
                ),
            )
            link_id = cursor.lastrowid
        return self.get_nav_hub_link(link_id)  # type: ignore

    def update_nav_hub_link(self, link_id: int, updates: dict) -> dict:
        """Update a nav hub link."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_nav_hub_link(link_id)
        if not existing:
            raise ValueError(f"Link '{link_id}' not found")

        fields = []
        values = []
        for field in ["category_id", "title", "url", "description", "sort_order", "enabled"]:
            if field in updates:
                fields.append(f"{field} = ?")
                values.append(updates[field] if field != "enabled" else (1 if updates[field] else 0))

        if fields:
            fields.append("updated_at = ?")
            values.append(now)
            values.append(link_id)
            with self.connect() as conn:
                conn.execute(f"UPDATE nav_hub_links SET {', '.join(fields)} WHERE id = ?", values)
        return self.get_nav_hub_link(link_id)  # type: ignore

    def delete_nav_hub_link(self, link_id: int) -> None:
        """Delete a nav hub link."""
        with self.connect() as conn:
            conn.execute("DELETE FROM nav_hub_links WHERE id = ?", (link_id,))

    def reorder_nav_hub_links(self, category_id: str, link_orders: list[dict]) -> None:
        """Reorder links within a category."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            for item in link_orders:
                conn.execute(
                    "UPDATE nav_hub_links SET sort_order = ?, updated_at = ? WHERE id = ? AND category_id = ?",
                    (item["sort_order"], now, item["id"], category_id),
                )

    # ==================== Collector Schedule ====================

    def get_collector_schedule(self) -> dict:
        """Get collector schedule config."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT enabled, interval_minutes, last_run_at, next_run_at, last_run_status, created_at, updated_at FROM collector_schedule WHERE id = 1"
            ).fetchone()
            if not row:
                # Create default config
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO collector_schedule (id, enabled, interval_minutes, created_at, updated_at) VALUES (1, 0, 60, ?, ?)",
                    (now, now),
                )
                return {
                    "enabled": False,
                    "interval_minutes": 60,
                    "last_run_at": None,
                    "next_run_at": None,
                    "last_run_status": None,
                }
            return {
                "enabled": bool(row[0]),
                "interval_minutes": row[1],
                "last_run_at": row[2],
                "next_run_at": row[3],
                "last_run_status": row[4],
            }

    def update_collector_schedule(self, updates: dict) -> dict:
        """Update collector schedule config."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            # Ensure row exists
            existing = conn.execute("SELECT id FROM collector_schedule WHERE id = 1").fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO collector_schedule (id, enabled, interval_minutes, created_at, updated_at) VALUES (1, 0, 60, ?, ?)",
                    (now, now),
                )

            fields = []
            values = []
            if "enabled" in updates:
                fields.append("enabled = ?")
                values.append(1 if updates["enabled"] else 0)
            if "interval_minutes" in updates:
                fields.append("interval_minutes = ?")
                values.append(updates["interval_minutes"])
            if "last_run_at" in updates:
                fields.append("last_run_at = ?")
                values.append(updates["last_run_at"])
            if "next_run_at" in updates:
                fields.append("next_run_at = ?")
                values.append(updates["next_run_at"])
            if "last_run_status" in updates:
                fields.append("last_run_status = ?")
                values.append(updates["last_run_status"])

            if fields:
                fields.append("updated_at = ?")
                values.append(now)
                conn.execute(f"UPDATE collector_schedule SET {', '.join(fields)} WHERE id = 1", values)

        return self.get_collector_schedule()

    # ==================== About Page Config ====================

    def get_about_config(self) -> dict[str, Any]:
        """Get about page configuration."""
        default_qr_code_url = "/wechat-qr.png" if DEFAULT_WECHAT_QR_PUBLIC_PATH.exists() else ""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT title, description, qr_code_url, follow_link, contact_info, links_json FROM about_config WHERE id = 1"
            ).fetchone()

        if row is None:
            return {
                "title": "",
                "description": "",
                "qr_code_url": default_qr_code_url,
                "follow_link": "",
                "contact_info": "",
                "links": [],
            }

        return {
            "title": row["title"],
            "description": row["description"],
            "qr_code_url": row["qr_code_url"] or default_qr_code_url,
            "follow_link": row["follow_link"],
            "contact_info": row["contact_info"],
            "links": json.loads(row["links_json"] or "[]"),
        }

    def update_about_config(
        self,
        *,
        title: str = "",
        description: str = "",
        qr_code_url: str = "",
        follow_link: str = "",
        contact_info: str = "",
        links: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Update about page configuration."""
        now = datetime.now(timezone.utc).isoformat()
        links_json = json.dumps(links or [], ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO about_config (id, title, description, qr_code_url, follow_link, contact_info, links_json, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    qr_code_url = excluded.qr_code_url,
                    follow_link = excluded.follow_link,
                    contact_info = excluded.contact_info,
                    links_json = excluded.links_json,
                    updated_at = excluded.updated_at
                """,
                (title, description, qr_code_url, follow_link, contact_info, links_json, now),
            )

        return self.get_about_config()


@lru_cache(maxsize=1)
def get_store() -> HotSQLiteStore:
    store = HotSQLiteStore()
    store.initialize()
    return store
