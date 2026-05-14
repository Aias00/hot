from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from hot_backend.collectors.models import (
    CollectRequest,
    DiscoveryCandidate,
    SourceConfig,
    SourceDocument,
)
from hot_backend.collectors.sources.base import build_item


def _text(node, path: str) -> str:
    child = node.find(path)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _parse_datetime(value: str):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except Exception:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None


def _atom_text(node, tag: str) -> str:
    namespaces = {"atom": "http://www.w3.org/2005/Atom"}
    child = node.find(f"atom:{tag}", namespaces)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _atom_attr(node, tag: str, attr: str) -> str:
    namespaces = {"atom": "http://www.w3.org/2005/Atom"}
    child = node.find(f"atom:{tag}", namespaces)
    if child is None:
        return ""
    return (child.get(attr) or "").strip()


def _iter_feed_items(tree: ElementTree.Element):
    rss_items = tree.findall("./channel/item")
    if rss_items:
        return ("rss", rss_items)

    atom_items = tree.findall("{http://www.w3.org/2005/Atom}entry")
    return ("atom", atom_items)


class RssGenericSourceAdapter:
    adapter_kind = "rss-generic"

    async def discover(
        self,
        source: SourceConfig,
        request: CollectRequest,
        checkpoint: dict,
    ) -> list[DiscoveryCandidate]:
        candidates: list[DiscoveryCandidate] = []
        timeout_seconds = int(source.config_json.get("timeout_seconds", 20) or 20)
        freshness_days = source.config_json.get("freshness_days")
        freshness_cutoff = None
        if isinstance(freshness_days, int) and freshness_days > 0:
            freshness_cutoff = datetime.now(UTC) - timedelta(days=freshness_days)

        for feed_url in source.seed_urls:
            request_obj = Request(
                feed_url,
                headers={"User-Agent": "hot-collect-rss-generic/0.1"},
            )
            with urlopen(request_obj, timeout=timeout_seconds) as response:
                tree = ElementTree.fromstring(response.read())

            feed_kind, items = _iter_feed_items(tree)
            for index, item in enumerate(items[: request.limit], start=1):
                if feed_kind == "rss":
                    title = _text(item, "title")
                    link = _text(item, "link")
                    guid = _text(item, "guid") or link or f"{source.source_id}-{index}"
                    summary = _text(item, "description")
                    author = _text(item, "author")
                    published_at = _text(item, "pubDate")
                    categories = [
                        category.text.strip()
                        for category in item.findall("category")
                        if category.text and category.text.strip()
                    ]
                else:
                    title = _atom_text(item, "title")
                    link = _atom_attr(item, "link", "href")
                    guid = _atom_text(item, "id") or link or f"{source.source_id}-{index}"
                    summary = _atom_text(item, "summary") or _atom_text(item, "content")
                    author = _atom_text(item.find("{http://www.w3.org/2005/Atom}author"), "name") if item.find("{http://www.w3.org/2005/Atom}author") is not None else ""
                    published_at = _atom_text(item, "updated") or _atom_text(item, "published")
                    categories = [
                        (category.get("term") or "").strip()
                        for category in item.findall("{http://www.w3.org/2005/Atom}category")
                        if (category.get("term") or "").strip()
                    ]

                published_dt = _parse_datetime(published_at)
                if freshness_cutoff and published_dt and published_dt < freshness_cutoff:
                    continue

                candidates.append(
                    DiscoveryCandidate(
                        candidate_id=f"{source.source_id}:{guid}",
                        source_url=link or feed_url,
                        external_id=guid,
                        metadata={
                            "title": title,
                            "summary": summary,
                            "author": author,
                            "published_at": published_at,
                            "categories": categories,
                            "feed_url": feed_url,
                            "feed_kind": feed_kind,
                        },
                    )
                )

        return candidates[: request.limit]

    async def hydrate(
        self,
        source: SourceConfig,
        candidates: list[DiscoveryCandidate],
    ) -> list[SourceDocument]:
        return [
            SourceDocument(
                candidate_id=candidate.candidate_id,
                source_url=candidate.source_url,
                title=candidate.metadata.get("title") or candidate.external_id or candidate.candidate_id,
                body=candidate.metadata.get("summary") or "",
                author=candidate.metadata.get("author") or None,
                published_at=_parse_datetime(candidate.metadata.get("published_at") or ""),
                metadata=dict(candidate.metadata),
            )
            for candidate in candidates
        ]

    async def normalize(self, source: SourceConfig, documents: list[SourceDocument]):
        return [
            build_item(
                source=source,
                external_id=document.metadata.get("feed_url") + "::" + document.candidate_id,
                canonical_url=document.source_url,
                title=document.title,
                summary=document.body or document.title,
                published_at=document.published_at,
                author=document.author,
                tags=document.metadata.get("categories") or [],
            )
            for document in documents
        ]
