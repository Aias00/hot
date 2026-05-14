from __future__ import annotations

import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from hot_backend.collectors.models import (
    CollectRequest,
    DiscoveryCandidate,
    SourceConfig,
    SourceDocument,
)
from hot_backend.collectors.sources.base import build_item


class _MpTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_row = False
        self._in_cell = False
        self._current_cell_text: list[str] = []
        self._current_row: list[dict[str, str]] = []
        self._current_href = ""
        self.rows: list[list[dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell_text = []
            self._current_href = ""
        elif self._in_cell and tag == "a":
            href = dict(attrs).get("href") or ""
            if href and not self._current_href:
                self._current_href = href

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._in_row and tag in {"td", "th"} and self._in_cell:
            text = " ".join(part.strip() for part in self._current_cell_text if part.strip()).strip()
            self._current_row.append({"text": text, "href": self._current_href})
            self._in_cell = False
            self._current_cell_text = []
            self._current_href = ""
        elif tag == "tr" and self._in_row:
            if len(self._current_row) == 7 and self._current_row[0]["text"] != "发文日期":
                self.rows.append(self._current_row)
            self._current_row = []
            self._in_row = False


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_anchor = False
        self._current_text: list[str] = []
        self._current_href = ""
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._in_anchor = True
            self._current_text = []
            self._current_href = dict(attrs).get("href") or ""

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_anchor:
            text = " ".join(part.strip() for part in self._current_text if part.strip()).strip()
            self.anchors.append({"text": text, "href": self._current_href})
            self._in_anchor = False
            self._current_text = []
            self._current_href = ""


def _normalize_row(row: list[dict[str, str]], index: int) -> dict[str, str | int]:
    return {
        "published_date": row[0]["text"],
        "title": row[1]["text"],
        "href": row[1]["href"],
        "account": row[2]["text"],
        "account_href": row[2]["href"],
        "reads": row[3]["text"],
        "likes": row[4]["text"],
        "shares": row[5]["text"],
        "outlier": row[6]["text"],
        "sequence": index,
    }


def _host_is_trusted(url: str, trusted_hosts: list[str] | None) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False

    if not trusted_hosts:
        return True

    host = (parsed.hostname or "").lower()
    for trusted_host in trusted_hosts:
        normalized = trusted_host.strip().lower()
        if not normalized:
            continue
        if host == normalized or host.endswith(f".{normalized}"):
            return True

    return False


def _looks_like_home_shell(raw_text: str) -> bool:
    return (
        "全部 AI 动态" in raw_text
        and "公众号爆文" not in raw_text
        and "<table" not in raw_text
    )


class MpHotSnapshotSourceAdapter:
    adapter_kind = "mp-hot-snapshot"

    def _read_text(self, source_url: str, source: SourceConfig) -> str:
        parsed = urlparse(source_url)
        timeout_seconds = int(source.config_json.get("timeout_seconds", 20) or 20)
        if parsed.scheme == "file":
            return Path(parsed.path).read_text(encoding="utf-8")
        if parsed.scheme in {"http", "https"}:
            request = Request(
                source_url,
                headers={"User-Agent": "hot-collect-mp-hot-snapshot/0.1"},
            )
            with urlopen(request, timeout=timeout_seconds) as response:
                return response.read().decode("utf-8", errors="ignore")
        raise ValueError(f"mp-hot-snapshot unsupported url scheme: {source_url}")

    def _load_rows(self, source: SourceConfig) -> list[dict[str, str | int]]:
        fallback_from_remote = False
        fallback_mode = "snapshot-json-fallback"
        for source_url in source.seed_urls:
            raw_text = self._read_text(source_url, source)
            stripped = raw_text.lstrip()

            if stripped.startswith("{"):
                payload = json.loads(raw_text)
                rows = payload.get("rows", [])
                if rows:
                    return [
                        {
                            "published_date": row[0],
                            "title": row[1],
                            "href": "",
                            "account": row[2],
                            "account_href": "",
                            "reads": row[3],
                            "likes": row[4],
                            "shares": row[5],
                            "outlier": row[6],
                            "sequence": index,
                            "source_mode": (
                                fallback_mode
                                if fallback_from_remote
                                else "snapshot-json"
                            ),
                            "seed_url": source_url,
                        }
                        for index, row in enumerate(rows, start=1)
                    ]
                continue

            parser = _MpTableParser()
            parser.feed(raw_text)
            if parser.rows:
                normalized_rows = []
                for index, row in enumerate(parser.rows, start=1):
                    normalized = _normalize_row(row, index)
                    normalized["source_mode"] = "html-table"
                    normalized["seed_url"] = source_url
                    normalized_rows.append(normalized)
                return normalized_rows

            if urlparse(source_url).scheme in {"http", "https"}:
                fallback_from_remote = True
                fallback_mode = (
                    "snapshot-json-home-shell-fallback"
                    if _looks_like_home_shell(raw_text)
                    else "snapshot-json-fallback"
                )

        return []

    def _resolve_detail_links(
        self,
        detail_url: str,
        source: SourceConfig,
    ) -> tuple[str | None, str | None]:
        if not detail_url:
            return (None, None)

        raw_text = self._read_text(detail_url, source)
        parser = _AnchorParser()
        parser.feed(raw_text)

        article_href = None
        account_href = None

        for anchor in parser.anchors:
            text = anchor["text"]
            href = anchor["href"]
            if not href:
                continue
            if article_href is None and any(keyword in text for keyword in ("查看原文", "原文")):
                article_href = href
                continue
            if account_href is None and any(keyword in text for keyword in ("账号", "主页")):
                account_href = href

        if article_href is None:
            for anchor in parser.anchors:
                href = anchor["href"]
                if href and href != detail_url:
                    article_href = href
                    break

        trusted_article_hosts = source.config_json.get("trusted_article_hosts")
        trusted_account_hosts = source.config_json.get("trusted_account_hosts")
        if article_href and not _host_is_trusted(article_href, trusted_article_hosts):
            article_href = None
        if account_href and not _host_is_trusted(account_href, trusted_account_hosts):
            account_href = None

        return (article_href, account_href)

    async def discover(
        self,
        source: SourceConfig,
        request: CollectRequest,
        checkpoint: dict,
    ) -> list[DiscoveryCandidate]:
        rows = self._load_rows(source)
        candidates: list[DiscoveryCandidate] = []

        for index, row in enumerate(rows[: request.limit], start=1):
            candidates.append(
                DiscoveryCandidate(
                    candidate_id=f"{source.source_id}:{row['published_date']}:{row['account']}:{index}",
                    source_url=str(row["href"] or ""),
                    external_id=f"{row['published_date']}:{row['account']}:{row['title']}",
                    metadata={
                        "published_date": row["published_date"],
                        "title": row["title"],
                        "account": row["account"],
                        "account_href": row["account_href"],
                        "reads": row["reads"],
                        "likes": row["likes"],
                        "shares": row["shares"],
                        "outlier": row["outlier"],
                        "sequence": index,
                        "source_mode": row["source_mode"],
                        "seed_url": row["seed_url"],
                    },
                )
            )

        return candidates

    async def hydrate(
        self,
        source: SourceConfig,
        candidates: list[DiscoveryCandidate],
    ) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        for candidate in candidates:
            published_date = candidate.metadata["published_date"]
            published_at = datetime.fromisoformat(f"{published_date}T08:00:00+00:00").astimezone(UTC)
            source_url = candidate.source_url
            metadata = dict(candidate.metadata)
            if (
                source.config_json.get("resolve_detail_links")
                and metadata.get("source_mode") == "html-table"
                and source_url
            ):
                article_href, account_href = self._resolve_detail_links(source_url, source)
                if article_href:
                    source_url = article_href
                if account_href and not metadata.get("account_href"):
                    metadata["account_href"] = account_href
            documents.append(
                SourceDocument(
                    candidate_id=candidate.candidate_id,
                    source_url=source_url,
                    title=metadata["title"],
                    body=(
                        f"{metadata['account']} · 阅读 {metadata['reads']} · "
                        f"点赞 {metadata['likes']} · 转发 {metadata['shares']}"
                    ),
                    author=metadata["account"],
                    published_at=published_at,
                    metadata=metadata,
                )
            )
        return documents

    async def normalize(self, source: SourceConfig, documents: list[SourceDocument]):
        items = []
        for document in documents:
            item = build_item(
                source=source,
                external_id=document.metadata["sequence"] and f"{document.metadata['published_date']}::{document.author}::{document.title}",
                canonical_url=document.source_url,
                title=document.title,
                summary=document.body or document.title,
                published_at=document.published_at,
                author=document.author,
                tags=["公众号爆文", "微信生态"],
            )
            item.content_type = "mp-article"
            item.metrics.update(
                {
                    "reads": document.metadata["reads"],
                    "likes": document.metadata["likes"],
                    "shares": document.metadata["shares"],
                    "outlier": document.metadata["outlier"],
                    "sequence": document.metadata["sequence"],
                    "badge": "采集",
                }
            )
            item.raw_ref.update(
                {
                    "published_date": document.metadata["published_date"],
                    "account": document.metadata["account"],
                    "account_href": document.metadata.get("account_href", ""),
                    "source_mode": document.metadata.get("source_mode", "snapshot-json"),
                    "seed_url": document.metadata.get("seed_url", ""),
                }
            )
            items.append(item)
        return items
