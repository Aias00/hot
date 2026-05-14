from __future__ import annotations

from datetime import UTC, datetime

from hot_backend.collectors.models import NormalizedHotItem, SourceConfig


_CATEGORY_LABELS = {
    "official": "官方信源",
    "blog": "博客文章",
    "wechat": "公众号榜单",
    "sample": "样例来源",
    "mock": "框架验证",
    "generic": "通用来源",
}

_CATEGORY_SCORES = {
    "official": 22,
    "blog": 14,
    "wechat": 18,
    "sample": 10,
    "mock": 2,
    "generic": 8,
}

_KEYWORD_BONUSES = {
    "发布": 6,
    "上线": 6,
    "更新": 5,
    "release": 6,
    "launch": 6,
    "ship": 5,
    "introducing": 5,
}


def _infer_source_category(source: SourceConfig) -> str:
    configured = str(source.config_json.get("category") or "").strip().lower()
    if configured in _CATEGORY_LABELS:
        return configured
    if source.adapter_kind == "mock-hot-source":
        return "mock"
    if source.config_json.get("mode") == "sample" or source.source_id.endswith("-sample"):
        return "sample"
    return "generic"


def _freshness_signal(published_at: datetime | None) -> tuple[int, str]:
    if not published_at:
        return (2, "时间未知")

    delta = datetime.now(UTC) - published_at.astimezone(UTC)
    if delta.days <= 0:
        return (18, "当日热点")
    if delta.days <= 3:
        return (14, "近 3 天内")
    if delta.days <= 7:
        return (10, "近 7 天内")
    if delta.days <= 30:
        return (6, "近 30 天内")
    return (2, "较早内容")


def _keyword_bonus(item: NormalizedHotItem) -> tuple[int, str | None]:
    haystack = f"{item.title} {item.summary}".lower()
    for keyword, score in _KEYWORD_BONUSES.items():
        if keyword.lower() in haystack:
            return (score, f"命中关键词“{keyword}”")
    return (0, None)


def enrich_item(source: SourceConfig, item: NormalizedHotItem) -> NormalizedHotItem:
    category = _infer_source_category(source)
    category_label = _CATEGORY_LABELS[category]
    freshness_score, freshness_label = _freshness_signal(item.published_at)
    keyword_score, keyword_label = _keyword_bonus(item)
    tag_score = min(len(item.tags), 4) * 3
    summary_score = 6 if len(item.summary) >= 80 else 3 if item.summary else 0

    hot_score = min(
        99,
        40
        + _CATEGORY_SCORES[category]
        + freshness_score
        + keyword_score
        + tag_score
        + summary_score,
    )

    reason_parts = [category_label, freshness_label]
    if item.tags:
        reason_parts.append(f"{min(len(item.tags), 4)} 个标签信号")
    if keyword_label:
        reason_parts.append(keyword_label)

    item.metrics.update(
        {
            "source_category": category,
            "source_category_label": category_label,
            "hot_score": hot_score,
            "reason": " · ".join(reason_parts),
        }
    )
    return item
