from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from hot_backend.app import create_app
from hot_backend.auth import TokenPayload
from hot_backend.auth import get_current_admin
from hot_backend.sqlite_store import HotSQLiteStore, MP_SEED_PATH, RSS_GENERIC_SAMPLE_PATH, get_store


class _FeedHandler(BaseHTTPRequestHandler):
    feed_payload = b""

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.feed_payload)

    def log_message(self, format, *args):  # noqa: A003
        return


class _MpHtmlHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/rankings":
            payload = """<!doctype html>
<html lang="zh-CN">
  <body>
    <table>
      <thead>
        <tr>
          <th>发文日期</th><th>标题</th><th>公众号</th><th>阅读</th><th>点赞</th><th>转发</th><th>异常值</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>2026-05-13</td>
          <td><a href="http://127.0.0.1:%PORT%/detail/article-1">详情页文章</a></td>
          <td>详情公众号</td>
          <td>54321</td>
          <td>432</td>
          <td>2100</td>
          <td>9</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
""".replace("%PORT%", str(self.server.server_address[1]))
        elif self.path == "/detail/article-1":
            payload = """<!doctype html>
<html lang="zh-CN">
  <body>
    <article>
      <a href="https://example.com/articles/final-article">查看原文</a>
      <a href="https://example.com/accounts/final-account">账号主页</a>
    </article>
  </body>
</html>
"""
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A003
        return


class _MpFallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        payload = """<!doctype html>
<html lang="zh-CN">
  <body>
    <nav>全部 AI 动态</nav>
    <main>首页外壳</main>
  </body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A003
        return


def _purge_test_source(source_id: str) -> None:
    store = get_store()
    with store.connect() as connection:
        run_rows = connection.execute(
            "SELECT run_id FROM collector_runs WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        run_ids = [row["run_id"] for row in run_rows]
        if run_ids:
            connection.executemany(
                "DELETE FROM collector_run_events WHERE run_id = ?",
                [(run_id,) for run_id in run_ids],
            )
        connection.execute("DELETE FROM collector_runs WHERE source_id = ?", (source_id,))
        connection.execute("DELETE FROM collector_checkpoints WHERE source_id = ?", (source_id,))
        connection.execute("DELETE FROM hot_items WHERE source_id = ?", (source_id,))
        connection.execute("DELETE FROM collector_sources WHERE source_id = ?", (source_id,))


def _clear_nav_hub_seed_tables() -> None:
    store = get_store()
    with store.connect() as connection:
        connection.execute("DELETE FROM nav_hub_links")
        connection.execute("DELETE FROM nav_hub_categories")


def _create_sample_rss_source(client: TestClient, source_id: str) -> None:
    response = client.post(
        "/api/collect/sources",
        json={
            "source_id": source_id,
            "adapter_kind": "rss-generic",
            "title": "Sample RSS Source",
            "description": "Temporary sample rss source for tests.",
            "enabled": True,
            "seed_urls": [RSS_GENERIC_SAMPLE_PATH.as_uri()],
            "config_json": {"mode": "sample"},
        },
    )
    assert response.status_code == 201


def test_nav_hub_public_api_is_seeded_when_tables_are_empty() -> None:
    _clear_nav_hub_seed_tables()
    get_store().seed_nav_hub_categories()

    client = TestClient(create_app())
    response = client.get("/api/nav-hub")

    assert response.status_code == 200
    categories = response.json()
    assert len(categories) >= 6
    assert categories[0]["id"] == "dev"
    assert categories[0]["links"][0]["title"] == "GitHub"


def test_store_backfills_about_navigation_and_old_about_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    store = HotSQLiteStore(db_path)

    with store.connect() as connection:
      connection.executescript(
          """
          CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
          );
          CREATE TABLE navigation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            icon TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL,
            "to" TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
          );
          CREATE TABLE about_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            qr_code_url TEXT NOT NULL DEFAULT '',
            follow_link TEXT NOT NULL DEFAULT '',
            contact_info TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
          );
          """
      )
      connection.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '1')")
      connection.execute(
          """
          INSERT INTO navigation_items (icon, label, "to", sort_order, enabled, created_at, updated_at)
          VALUES ('◫', '导航中心', '/nav-hub', 0, 1, '2026-05-17T00:00:00+00:00', '2026-05-17T00:00:00+00:00')
          """
      )
      connection.execute(
          """
          INSERT INTO navigation_items (icon, label, "to", sort_order, enabled, created_at, updated_at)
          VALUES ('☰', '全部 AI 动态', '/all', 1, 1, '2026-05-17T00:00:00+00:00', '2026-05-17T00:00:00+00:00')
          """
      )
      connection.execute(
          """
          INSERT INTO about_config (id, title, description, qr_code_url, follow_link, contact_info, updated_at)
          VALUES (1, '关于', 'desc', '', '', '', '2026-05-17T00:00:00+00:00')
          """
      )

    store.initialize()

    nav_items = store.list_navigation_items()
    assert any(item["to"] == "/about" and item["enabled"] for item in nav_items)

    about_config = store.get_about_config()
    assert about_config["title"] == "关于"
    assert isinstance(about_config["links"], list)
    assert about_config["qr_code_url"] == "/wechat-qr.png"


def test_admin_schedule_update_applies_scheduler_config(monkeypatch: pytest.MonkeyPatch) -> None:
    applied: dict[str, bool] = {"called": False}

    def fake_update_scheduler_config(*, enabled=None, interval_minutes=None):
        return {
            "enabled": enabled,
            "interval_minutes": interval_minutes,
            "last_run_at": None,
            "next_run_at": None,
            "last_run_status": None,
        }

    async def fake_apply_scheduler_config():
        applied["called"] = True

    app = create_app()
    app.dependency_overrides[get_current_admin] = lambda: TokenPayload(sub="admin", iat=0, exp=4102444800)
    monkeypatch.setattr("hot_backend.scheduler.update_scheduler_config", fake_update_scheduler_config)
    monkeypatch.setattr("hot_backend.scheduler.apply_scheduler_config", fake_apply_scheduler_config)

    client = TestClient(app)
    response = client.put("/api/admin/schedule", json={"enabled": True, "interval_minutes": 60})

    assert response.status_code == 200
    assert applied["called"] is True


def test_app_startup_applies_scheduler_config(monkeypatch: pytest.MonkeyPatch) -> None:
    applied: dict[str, bool] = {"startup": False, "shutdown": False}

    async def fake_apply_scheduler_config():
        applied["startup"] = True

    def fake_stop_scheduler():
        applied["shutdown"] = True

    monkeypatch.setattr("hot_backend.app.apply_scheduler_config", fake_apply_scheduler_config)
    monkeypatch.setattr("hot_backend.app.stop_scheduler", fake_stop_scheduler)

    with TestClient(create_app()):
        pass

    assert applied["startup"] is True
    assert applied["shutdown"] is True


def _create_mp_snapshot_source(client: TestClient, source_id: str) -> None:
    response = client.post(
        "/api/collect/sources",
        json={
            "source_id": source_id,
            "adapter_kind": "mp-hot-snapshot",
            "title": "Temporary MP Snapshot Source",
            "description": "Temporary mp snapshot source for tests.",
            "enabled": True,
            "seed_urls": [MP_SEED_PATH.as_uri()],
            "config_json": {
                "category": "wechat",
                "timeout_seconds": 20,
                "trusted_article_hosts": ["mp.weixin.qq.com", "weixin.qq.com"],
                "trusted_account_hosts": ["mp.weixin.qq.com", "weixin.qq.com"],
                "ranking_weights": {
                    "reads_divisor": 100,
                    "likes_multiplier": 2,
                    "shares_multiplier": 0.5,
                    "outlier_multiplier": 20,
                },
            },
        },
    )
    assert response.status_code == 201


def test_collect_sources_expose_only_default_rss_sources():
    client = TestClient(create_app())

    response = client.get("/api/collect/sources")

    assert response.status_code == 200
    payload = response.json()
    source_ids = {item["source_id"] for item in payload["items"]}
    assert source_ids == {
        "openai-news-rss",
        "github-blog-rss",
        "huggingface-blog-rss",
        "google-developers-blog-rss",
        "google-deepmind-news-rss",
        "google-blog-ai-rss",
        "google-blog-deepmind-rss",
        "google-developers-tech-blog-rss",
        "vercel-news-rss",
        "replicate-blog-rss",
        "aws-machine-learning-blog-rss",
        "sambanova-blog-rss",
        "microsoft-foundry-blog-rss",
        "langgraph-blog-rss",
        "kaggle-blog-rss",
        "microsoft-semantic-kernel-blog-rss",
        "together-ai-blog-rss",
        "ollama-blog-rss",
        "midjourney-updates-rss",
    }


def test_collect_adapter_kinds_expose_only_rss_generic():
    client = TestClient(create_app())

    response = client.get("/api/collect/adapter-kinds")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == ["rss-generic"]


def test_execute_sample_rss_source_dry_run(tmp_path: Path):
    client = TestClient(create_app())
    source_id = f"rss-sample-{uuid4().hex[:8]}"

    try:
        _create_sample_rss_source(client, source_id)
        response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": True,
                "limit": 2,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["workflow"] == "hot-collect"
        assert payload["status"] == "completed"
        assert payload["summary"]["discovered_count"] == 2
        assert payload["summary"]["hydrated_count"] == 2
        assert payload["summary"]["normalized_count"] == 2
    finally:
        _purge_test_source(source_id)


def test_execute_sample_rss_source_persists_to_feed(tmp_path: Path):
    client = TestClient(create_app())
    source_id = f"rss-sample-persist-{uuid4().hex[:8]}"

    try:
        _create_sample_rss_source(client, source_id)
        response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 1,
            },
        )

        assert response.status_code == 200

        feed_response = client.get("/api/feed")
        assert feed_response.status_code == 200
        feed_payload = feed_response.json()
        sample_item = next(
            item
            for item in feed_payload["items"]
            if item["title"] == "OpenAI ships a smaller realtime voice model"
            and item.get("sourceId") == source_id
        )
        assert sample_item["badge"] == "采集"
        assert "Mock" not in sample_item["title"]
        assert sample_item["source"] == "OpenAI"
    finally:
        _purge_test_source(source_id)


def test_feed_endpoint_supports_query_and_pagination():
    client = TestClient(create_app())
    source_id = f"rss-feed-page-{uuid4().hex[:8]}"

    try:
        _create_sample_rss_source(client, source_id)
        response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 2,
            },
        )
        assert response.status_code == 200

        feed_response = client.get(
            "/api/feed?q=realtime%20voice&page=1&limit=1"
        )
        assert feed_response.status_code == 200
        payload = feed_response.json()
        assert payload["count"] == 1
        assert payload["page"] == 1
        assert payload["page_size"] == 1
        assert payload["total_count"] >= 1
        assert payload["items"][0]["title"] == "OpenAI ships a smaller realtime voice model"
    finally:
        _purge_test_source(source_id)


def test_can_create_and_execute_configurable_rss_source(tmp_path: Path):
    feed_path = tmp_path / "custom-feed.xml"
    feed_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Custom RSS Feed</title>
    <link>https://example.com/custom-feed</link>
    <description>Custom feed for configurable source test.</description>
    <item>
      <title>Custom source item</title>
      <link>https://example.com/custom-source-item</link>
      <guid>custom-source-item</guid>
      <pubDate>Tue, 13 May 2026 11:00:00 GMT</pubDate>
      <author>Custom Author</author>
      <category>Custom</category>
      <description>This item validates configurable rss-generic sources.</description>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"rss-generic-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "rss-generic",
                "title": "Configurable RSS Source",
                "description": "Configurable source for rss-generic execution test.",
                "enabled": True,
                "seed_urls": [feed_path.as_uri()],
                "config_json": {"mode": "test"},
            },
        )

        assert create_response.status_code == 201
        assert create_response.json()["source_id"] == source_id

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": True,
                "limit": 1,
            },
        )

        assert execute_response.status_code == 200
        payload = execute_response.json()
        assert payload["workflow"] == "hot-collect"
        assert payload["summary"]["discovered_count"] == 1
        assert payload["summary"]["normalized_count"] == 1
    finally:
        _purge_test_source(source_id)


def test_rss_generic_respects_freshness_days(tmp_path: Path):
    feed_path = tmp_path / "freshness-feed.xml"
    feed_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Freshness Feed</title>
    <link>https://example.com/freshness-feed</link>
    <description>Freshness filter validation.</description>
    <item>
      <title>Old item</title>
      <link>https://example.com/old-item</link>
      <guid>old-item</guid>
      <pubDate>Tue, 01 Apr 2026 08:00:00 GMT</pubDate>
      <description>Too old.</description>
    </item>
    <item>
      <title>Fresh item</title>
      <link>https://example.com/fresh-item</link>
      <guid>fresh-item</guid>
      <pubDate>Tue, 13 May 2026 08:00:00 GMT</pubDate>
      <description>Fresh enough.</description>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"rss-freshness-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "rss-generic",
                "title": "Freshness RSS Source",
                "description": "Freshness constrained source",
                "enabled": True,
                "seed_urls": [feed_path.as_uri()],
                "config_json": {"freshness_days": 7},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": True,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200
        payload = execute_response.json()
        assert payload["summary"]["discovered_count"] == 1
        assert payload["summary"]["normalized_count"] == 1
    finally:
        _purge_test_source(source_id)


def test_rejects_invalid_rss_seed_url_scheme():
    client = TestClient(create_app())

    response = client.post(
        "/api/collect/sources",
        json={
            "source_id": "invalid-rss-source",
            "adapter_kind": "rss-generic",
            "title": "Invalid RSS Source",
            "description": "Should fail validation",
            "enabled": True,
            "seed_urls": ["ftp://example.com/feed.xml"],
            "config_json": {},
        },
    )

    assert response.status_code == 400
    assert "unsupported rss-generic URL scheme" in response.json()["detail"]


def test_can_create_execute_and_delete_http_rss_source():
    _FeedHandler.feed_payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>HTTP RSS Feed</title>
    <link>https://example.com/http-feed</link>
    <description>HTTP served feed.</description>
    <item>
      <title>HTTP served item</title>
      <link>https://example.com/http-item</link>
      <guid>http-item</guid>
      <pubDate>Tue, 13 May 2026 12:00:00 GMT</pubDate>
      <author>HTTP Author</author>
      <category>HTTP</category>
      <description>Served over http for adapter validation.</description>
    </item>
  </channel>
</rss>"""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FeedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = TestClient(create_app())
    source_id = f"http-rss-{uuid4().hex[:8]}"
    feed_url = f"http://127.0.0.1:{server.server_address[1]}/feed.xml"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "rss-generic",
                "title": "HTTP RSS Source",
                "description": "HTTP feed source",
                "enabled": True,
                "seed_urls": [feed_url],
                "config_json": {},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": True,
                "limit": 1,
            },
        )
        assert execute_response.status_code == 200
        assert execute_response.json()["summary"]["discovered_count"] == 1

        update_response = client.put(
            f"/api/collect/sources/{source_id}",
            json={
                "title": "Updated HTTP RSS Source",
                "description": "Updated HTTP feed source",
                "enabled": False,
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["title"] == "Updated HTTP RSS Source"
        assert update_response.json()["enabled"] is False

        delete_response = client.delete(f"/api/collect/sources/{source_id}")
        assert delete_response.status_code == 204
    finally:
        server.shutdown()
        server.server_close()


def test_rss_summary_html_is_sanitized_in_feed(tmp_path: Path):
    feed_path = tmp_path / "html-summary-feed.xml"
    feed_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>HTML Summary Feed</title>
    <link>https://example.com/html-feed</link>
    <description>HTML summary cleanup validation.</description>
    <item>
      <title>HTML summary item</title>
      <link>https://example.com/html-summary-item</link>
      <guid>html-summary-item</guid>
      <pubDate>Tue, 13 May 2026 12:30:00 GMT</pubDate>
      <description><![CDATA[<p>Alpha <a href="https://example.com">Beta</a> &amp; <strong>Gamma</strong>.</p>]]></description>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"rss-html-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "rss-generic",
                "title": "HTML Summary RSS Source",
                "description": "HTML summary cleanup source",
                "enabled": True,
                "seed_urls": [feed_path.as_uri()],
                "config_json": {},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 1,
            },
        )
        assert execute_response.status_code == 200

        feed_response = client.get("/api/feed")
        assert feed_response.status_code == 200
        item = next(
            entry
            for entry in feed_response.json()["items"]
            if entry["title"] == "HTML summary item"
            and entry.get("sourceId") == source_id
        )
        assert item["body"] == "Alpha Beta & Gamma."
    finally:
        _purge_test_source(source_id)


def test_rss_summary_boilerplate_is_removed_from_feed(tmp_path: Path):
    feed_path = tmp_path / "boilerplate-feed.xml"
    feed_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Boilerplate Feed</title>
    <link>https://example.com/boilerplate-feed</link>
    <description>Boilerplate cleanup validation.</description>
    <item>
      <title>Boilerplate summary item</title>
      <link>https://example.com/boilerplate-item</link>
      <guid>boilerplate-item</guid>
      <pubDate>Tue, 13 May 2026 13:00:00 GMT</pubDate>
      <description><![CDATA[<p>Primary summary sentence.</p><p>The post <a href="https://example.com/boilerplate-item">Boilerplate summary item</a> appeared first on <a href="https://example.com">The Example Blog</a>.</p>]]></description>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"rss-boilerplate-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "rss-generic",
                "title": "Boilerplate RSS Source",
                "description": "Boilerplate cleanup source",
                "enabled": True,
                "seed_urls": [feed_path.as_uri()],
                "config_json": {},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 1,
            },
        )
        assert execute_response.status_code == 200

        feed_response = client.get("/api/feed")
        assert feed_response.status_code == 200
        item = next(
            entry
            for entry in feed_response.json()["items"]
            if entry["title"] == "Boilerplate summary item"
            and entry.get("sourceId") == source_id
        )
        assert item["body"] == "Primary summary sentence."
    finally:
        _purge_test_source(source_id)


def test_collect_enriches_item_with_category_score_and_reason(tmp_path: Path):
    feed_path = tmp_path / "enriched-feed.xml"
    feed_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Enriched Feed</title>
    <link>https://example.com/enriched-feed</link>
    <description>Enrichment validation feed.</description>
    <item>
      <title>Enriched summary item</title>
      <link>https://example.com/enriched-item</link>
      <guid>enriched-item</guid>
      <pubDate>Tue, 13 May 2026 14:00:00 GMT</pubDate>
      <category>Agent</category>
      <description><![CDATA[<p>Detailed launch note for a new agent workflow.</p>]]></description>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"rss-enriched-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "rss-generic",
                "title": "Enriched RSS Source",
                "description": "Enrichment source",
                "enabled": True,
                "seed_urls": [feed_path.as_uri()],
                "config_json": {"category": "official"},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 1,
            },
        )
        assert execute_response.status_code == 200

        collected_response = client.get(
            "/api/collected",
            params={"source_id": source_id, "limit": 5},
        )
        assert collected_response.status_code == 200
        collected_item = collected_response.json()["items"][0]
        assert collected_item["source_category"] == "official"
        assert collected_item["source_category_label"] == "官方信源"
        assert collected_item["hot_score"] >= 70
        assert "官方信源" in collected_item["reason"]

        feed_response = client.get("/api/feed")
        assert feed_response.status_code == 200
        feed_item = next(
            entry
            for entry in feed_response.json()["items"]
            if entry["title"] == "Enriched summary item"
            and entry.get("sourceId") == source_id
        )
        assert feed_item["score"].isdigit()
        assert feed_item["reason"] != "由 hot-collect 采集流程导入。"
    finally:
        _purge_test_source(source_id)


def test_execute_mp_hot_snapshot_switches_mp_api_to_collector_model():
    client = TestClient(create_app())
    source_id = f"mp-hot-default-{uuid4().hex[:8]}"

    try:
        _create_mp_snapshot_source(client, source_id)
        response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 20,
            },
        )
        assert response.status_code == 200

        mp_response = client.get(
            "/api/mp",
            params={"since": "all", "page": 1},
        )
        assert mp_response.status_code == 200
        payload = mp_response.json()
        assert payload["source"] == "collector"
        assert payload["rows"][0]["badge"] == "采集"
        assert payload["pageMeta"][1] in {
            "来源：本地快照回退",
            "来源：HTML 榜单解析",
            "来源：远程页不可用，回退本地快照",
            "来源：远程路由返回首页壳，回退本地快照",
        }
        assert "排序：热度排序" in payload["pageMeta"]
        assert payload["rows"][0]["account"]
        assert payload["rows"][0]["reads"]
        assert payload["rows"][0]["title"]
    finally:
        _purge_test_source(source_id)


def test_mp_hot_snapshot_can_parse_html_source(tmp_path: Path):
    html_path = tmp_path / "mp-hot.html"
    html_path.write_text(
        """<!doctype html>
<html lang="zh-CN">
  <body>
    <table>
      <thead>
        <tr>
          <th>发文日期</th><th>标题</th><th>公众号</th><th>阅读</th><th>点赞</th><th>转发</th><th>异常值</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>2026-05-13</td>
          <td><a href="https://example.com/articles/mp-real">真实榜单文章</a></td>
          <td><a href="https://example.com/accounts/mp-real">真实公众号</a></td>
          <td>54321</td>
          <td>432</td>
          <td>2100</td>
          <td>9</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"mp-hot-html-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "mp-hot-snapshot",
                "title": "MP HTML Source",
                "description": "HTML-backed mp source",
                "enabled": True,
                "seed_urls": [html_path.as_uri()],
                "config_json": {},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200

        mp_response = client.get("/api/mp", params={"since": "all", "page": 1})
        assert mp_response.status_code == 200
        payload = mp_response.json()
        row = next(item for item in payload["rows"] if item["title"] == "真实榜单文章")
        assert row["href"] == "https://example.com/articles/mp-real"
        assert row["account"] == "真实公众号"
        assert row["accountHref"] == "https://example.com/accounts/mp-real"
        assert row["reads"] == "54321"
    finally:
        _purge_test_source(source_id)


def test_mp_hot_snapshot_can_resolve_second_hop_links():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MpHtmlHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = TestClient(create_app())
    source_id = f"mp-hot-second-hop-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "mp-hot-snapshot",
                "title": "MP Second Hop Source",
                "description": "HTML-backed mp source with detail page hop",
                "enabled": True,
                "seed_urls": [f"http://127.0.0.1:{server.server_address[1]}/rankings"],
                "config_json": {
                    "resolve_detail_links": True,
                    "trusted_article_hosts": ["example.com"],
                    "trusted_account_hosts": ["example.com"],
                },
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200

        mp_response = client.get("/api/mp", params={"since": "all", "page": 1})
        assert mp_response.status_code == 200
        payload = mp_response.json()
        row = next(item for item in payload["rows"] if item["title"] == "详情页文章")
        assert row["href"] == "https://example.com/articles/final-article"
        assert row["accountHref"] == "https://example.com/accounts/final-account"
    finally:
        _purge_test_source(source_id)
        server.shutdown()
        server.server_close()


def test_mp_hot_snapshot_rejects_second_hop_links_outside_whitelist():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MpHtmlHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = TestClient(create_app())
    source_id = f"mp-hot-untrusted-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "mp-hot-snapshot",
                "title": "MP Untrusted Source",
                "description": "HTML-backed mp source with blocked second hop",
                "enabled": True,
                "seed_urls": [f"http://127.0.0.1:{server.server_address[1]}/rankings"],
                "config_json": {
                    "resolve_detail_links": True,
                    "trusted_article_hosts": ["trusted.example.com"],
                    "trusted_account_hosts": ["trusted.example.com"],
                },
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200

        mp_response = client.get("/api/mp", params={"since": "all", "page": 1})
        assert mp_response.status_code == 200
        payload = mp_response.json()
        row = next(item for item in payload["rows"] if item["title"] == "详情页文章")
        assert row["href"] == f"http://127.0.0.1:{server.server_address[1]}/detail/article-1"
        assert row["accountHref"] == ""
    finally:
        _purge_test_source(source_id)
        server.shutdown()
        server.server_close()


def test_mp_hot_snapshot_orders_rows_by_heat_score(tmp_path: Path):
    html_path = tmp_path / "mp-ranking.html"
    html_path.write_text(
        """<!doctype html>
<html lang="zh-CN">
  <body>
    <table>
      <thead>
        <tr>
          <th>发文日期</th><th>标题</th><th>公众号</th><th>阅读</th><th>点赞</th><th>转发</th><th>异常值</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>2026-05-13</td>
          <td><a href="https://example.com/articles/rank-a">排序测试 A</a></td>
          <td>测试号 A</td>
          <td>10000</td>
          <td>50</td>
          <td>100</td>
          <td>1</td>
        </tr>
        <tr>
          <td>2026-05-13</td>
          <td><a href="https://example.com/articles/rank-b">排序测试 B</a></td>
          <td>测试号 B</td>
          <td>8000</td>
          <td>500</td>
          <td>800</td>
          <td>10</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"mp-hot-ranking-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "mp-hot-snapshot",
                "title": "MP Ranking Source",
                "description": "HTML-backed mp source for ranking validation",
                "enabled": True,
                "seed_urls": [html_path.as_uri()],
                "config_json": {},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200

        mp_response = client.get("/api/mp", params={"since": "all", "page": 1, "q": "排序测试"})
        assert mp_response.status_code == 200
        payload = mp_response.json()
        assert payload["rows"][0]["title"] == "排序测试 B"
    finally:
        _purge_test_source(source_id)


def test_mp_hot_snapshot_respects_custom_ranking_weights(tmp_path: Path):
    html_path = tmp_path / "mp-ranking-custom.html"
    html_path.write_text(
        """<!doctype html>
<html lang="zh-CN">
  <body>
    <table>
      <thead>
        <tr>
          <th>发文日期</th><th>标题</th><th>公众号</th><th>阅读</th><th>点赞</th><th>转发</th><th>异常值</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>2026-05-13</td>
          <td><a href="https://example.com/articles/custom-rank-a">自定义排序 A</a></td>
          <td>测试号 A</td>
          <td>10000</td>
          <td>50</td>
          <td>100</td>
          <td>1</td>
        </tr>
        <tr>
          <td>2026-05-13</td>
          <td><a href="https://example.com/articles/custom-rank-b">自定义排序 B</a></td>
          <td>测试号 B</td>
          <td>8000</td>
          <td>500</td>
          <td>800</td>
          <td>10</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
""",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    source_id = f"mp-hot-ranking-custom-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "mp-hot-snapshot",
                "title": "MP Ranking Custom Source",
                "description": "HTML-backed mp source for ranking weight validation",
                "enabled": True,
                "seed_urls": [html_path.as_uri()],
                "config_json": {
                    "ranking_weights": {
                        "reads_divisor": 1,
                        "likes_multiplier": 0,
                        "shares_multiplier": 0,
                        "outlier_multiplier": 0,
                    }
                },
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200

        mp_response = client.get("/api/mp", params={"since": "all", "page": 1, "q": "自定义排序"})
        assert mp_response.status_code == 200
        payload = mp_response.json()
        assert payload["rows"][0]["title"] == "自定义排序 A"
    finally:
        _purge_test_source(source_id)


def test_mp_hot_snapshot_fallback_mode_is_explicit_and_does_not_fake_links():
    client = TestClient(create_app())
    source_id = f"mp-hot-default-fallback-{uuid4().hex[:8]}"

    try:
        _create_mp_snapshot_source(client, source_id)
        response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 20,
            },
        )
        assert response.status_code == 200

        mp_response = client.get(
            "/api/mp",
            params={"since": "all", "page": 1},
        )
        assert mp_response.status_code == 200
        payload = mp_response.json()
        assert payload["source"] == "collector"
        assert "回退" in payload["pageMeta"][1]
        assert payload["rows"][0]["href"] == ""
    finally:
        _purge_test_source(source_id)


def test_mp_hot_snapshot_reports_remote_unavailable_before_snapshot_fallback(tmp_path: Path):
    json_path = tmp_path / "mp-fallback.json"
    json_path.write_text(
        json.dumps(
            {
                "rows": [
                    ["2026-05-13", "回退榜单条目", "回退公众号", "12345", "200", "600", "4"],
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), _MpFallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = TestClient(create_app())
    source_id = f"mp-hot-fallback-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "mp-hot-snapshot",
                "title": "MP Fallback Source",
                "description": "Remote html shell then snapshot fallback",
                "enabled": True,
                "seed_urls": [
                    f"http://127.0.0.1:{server.server_address[1]}/rankings",
                    json_path.as_uri(),
                ],
                "config_json": {},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200

        mp_response = client.get("/api/mp", params={"since": "all", "page": 1, "q": "回退榜单"})
        assert mp_response.status_code == 200
        payload = mp_response.json()
        assert payload["pageMeta"][1] == "来源：远程路由返回首页壳，回退本地快照"
    finally:
        _purge_test_source(source_id)
        server.shutdown()
        server.server_close()


def test_mp_hot_snapshot_execute_reports_source_modes_in_events(tmp_path: Path):
    json_path = tmp_path / "mp-event-fallback.json"
    json_path.write_text(
        json.dumps(
            {
                "rows": [
                    ["2026-05-13", "事件诊断条目", "诊断公众号", "12345", "200", "600", "4"],
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), _MpFallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client = TestClient(create_app())
    source_id = f"mp-hot-event-{uuid4().hex[:8]}"

    try:
        create_response = client.post(
            "/api/collect/sources",
            json={
                "source_id": source_id,
                "adapter_kind": "mp-hot-snapshot",
                "title": "MP Event Source",
                "description": "Fallback mode diagnostics source",
                "enabled": True,
                "seed_urls": [
                    f"http://127.0.0.1:{server.server_address[1]}/rankings",
                    json_path.as_uri(),
                ],
                "config_json": {},
            },
        )
        assert create_response.status_code == 201

        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": True,
                "limit": 10,
            },
        )
        assert execute_response.status_code == 200
        discover_event = next(
            event
            for event in execute_response.json()["events"]
            if event["node"] == "discover_candidates"
        )
        assert discover_event["payload"]["source_modes"] == {
            "snapshot-json-home-shell-fallback": 1
        }
    finally:
        _purge_test_source(source_id)
        server.shutdown()
        server.server_close()


def test_daily_latest_issue_prefers_collected_items(tmp_path: Path):
    client = TestClient(create_app())
    source_id = f"rss-daily-{uuid4().hex[:8]}"

    try:
        _create_sample_rss_source(client, source_id)
        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 1,
            },
        )
        assert execute_response.status_code == 200

        response = client.get(
            "/api/daily",
            params={"view": "issue", "date": "2026-05-08"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["sidebar"]["latest"]["date"].startswith("2026-05-")
        assert payload["masthead"]["date"].startswith("2026年5月")
        assert payload["masthead"]["tagline"] == "COLLECTED · hot-collect 采集快报"
        stories = [
            story
            for section in payload["sections"]
            for story in section["stories"]
        ]
        assert any(story["sourceRole"] == "采集" for story in stories)

        sample_issue_response = client.get(
            "/api/daily",
            params={"view": "issue", "date": "2026-05-13"},
        )
        assert sample_issue_response.status_code == 200
        sample_payload = sample_issue_response.json()
        sample_stories = [
            story
            for section in sample_payload["sections"]
            for story in section["stories"]
        ]
        assert any(
            story["title"] == "OpenAI ships a smaller realtime voice model"
            for story in sample_stories
        )
    finally:
        _purge_test_source(source_id)


def test_daily_archive_includes_collected_issue_first(tmp_path: Path):
    client = TestClient(create_app())
    source_id = f"rss-daily-archive-{uuid4().hex[:8]}"

    try:
        _create_sample_rss_source(client, source_id)
        execute_response = client.post(
            "/api/collect/execute",
            json={
                "source_id": source_id,
                "dry_run": False,
                "limit": 1,
            },
        )
        assert execute_response.status_code == 200

        response = client.get(
            "/api/daily",
            params={"view": "archive"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["archive"]["entries"][0]["href"] == "/daily"
        assert payload["archive"]["entries"][0]["date"].startswith("5月")
        assert payload["archive"]["entries"][0]["events"].endswith("事件")
    finally:
        _purge_test_source(source_id)


def test_collected_api_supports_multiple_source_ids():
    client = TestClient(create_app())
    first_source = f"rss-collected-a-{uuid4().hex[:8]}"
    second_source = f"rss-collected-b-{uuid4().hex[:8]}"

    try:
        _create_sample_rss_source(client, first_source)
        _create_sample_rss_source(client, second_source)
        for source_id in (first_source, second_source):
            response = client.post(
                "/api/collect/execute",
                json={
                    "source_id": source_id,
                    "dry_run": False,
                    "limit": 1,
                },
            )
            assert response.status_code == 200

        collected_response = client.get(
            "/api/collected",
            params={
                "source_ids": f"{first_source},{second_source}",
                "limit": 50,
            },
        )
        assert collected_response.status_code == 200
        payload = collected_response.json()
        assert payload["items"]
        assert {
            item["source_id"]
            for item in payload["items"]
        }.issubset({first_source, second_source})
    finally:
        _purge_test_source(first_source)
        _purge_test_source(second_source)
