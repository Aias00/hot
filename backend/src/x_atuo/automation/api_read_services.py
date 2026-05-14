from __future__ import annotations

from fastapi import HTTPException, Request, status

from x_atuo.automation.config import AutomationConfig
from x_atuo.core.twitter_client import TwitterClient, TwitterClientError
from x_atuo.core.x_web_analytics import (
    AnalyticsGranularity,
    ContentSortField,
    ContentType,
    SortDirection,
    XWebAnalyticsClient,
    build_account_analytics_snapshot,
    build_account_content_snapshot,
)
from x_atuo.core.x_web_notifications import (
    NotificationsTimelineType,
    XWebNotificationsClient,
    build_device_follow_feed_snapshot,
    build_notifications_snapshot,
)


def _get_account_analytics_snapshot(
    *,
    request: Request,
    days: int,
    post_limit: int,
    granularity: AnalyticsGranularity,
) -> dict[str, Any]:
    settings = request.app.state.settings
    client = XWebAnalyticsClient.from_settings(settings)
    return build_account_analytics_snapshot(
        client,
        days=days,
        post_limit=post_limit,
        granularity=granularity,
    )


def _get_account_content_snapshot(
    *,
    request: Request,
    from_date: str | None,
    to_date: str | None,
    content_type: ContentType,
    sort_field: ContentSortField,
    sort_direction: SortDirection,
    limit: int,
) -> dict[str, Any]:
    settings = request.app.state.settings
    client = XWebAnalyticsClient.from_settings(settings)
    return build_account_content_snapshot(
        client,
        from_date=from_date,
        to_date=to_date,
        content_type=content_type,
        sort_field=sort_field,
        sort_direction=sort_direction,
        limit=limit,
    )


def _get_notifications_snapshot(
    *,
    request: Request,
    timeline_type: NotificationsTimelineType,
    count: int,
    cursor: str | None,
) -> dict[str, Any]:
    settings = request.app.state.settings
    client = XWebNotificationsClient.from_settings(settings)
    return build_notifications_snapshot(
        client,
        timeline_type=timeline_type,
        count=count,
        cursor=cursor,
    )


def _get_device_follow_feed_snapshot(
    *,
    request: Request,
    count: int,
) -> dict[str, Any]:
    settings = request.app.state.settings
    client = XWebNotificationsClient.from_settings(settings)
    return build_device_follow_feed_snapshot(client, count=count)


def _build_runtime_twitter_client(settings: AutomationConfig) -> TwitterClient:
    return TwitterClient.from_config(
        settings.agent_reach_config_path,
        proxy=settings.twitter.proxy_url,
        twitter_bin=settings.twitter.cli_bin,
        timeout=120,
    )


def _handle_twitter_read_error(exc: Exception) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    if "twitter auth_token" in lowered or "twitter_ct0" in lowered or "not configured" in lowered:
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message)


def _normalize_tweet_record(tweet: Any) -> dict[str, Any]:
    if hasattr(tweet, "model_dump"):
        return tweet.model_dump(mode="json")
    if isinstance(tweet, dict):
        return dict(tweet)
    author = getattr(tweet, "author", None)
    return {
        "tweet_id": getattr(tweet, "tweet_id", None),
        "text": getattr(tweet, "text", None),
        "created_at": getattr(tweet, "created_at", None),
        "article_title": getattr(tweet, "article_title", None),
        "article_text": getattr(tweet, "article_text", None),
        "conversation_id": getattr(tweet, "conversation_id", None),
        "in_reply_to_tweet_id": getattr(tweet, "in_reply_to_tweet_id", None),
        "in_reply_to_screen_name": getattr(tweet, "in_reply_to_screen_name", None),
        "is_note_tweet": getattr(tweet, "is_note_tweet", None),
        "lang": getattr(tweet, "lang", None),
        "quoted_tweet_id": getattr(tweet, "quoted_tweet_id", None),
        "retweeted_tweet_id": getattr(tweet, "retweeted_tweet_id", None),
        "raw": getattr(tweet, "raw", None),
        "author": None
        if author is None
        else {
            "screen_name": getattr(author, "screen_name", None),
            "name": getattr(author, "name", None),
            "verified": getattr(author, "verified", None),
            "id": getattr(author, "id", None),
            "profile_image_url": getattr(author, "profile_image_url", None),
        },
    }


__all__ = [
    "_build_runtime_twitter_client",
    "_get_account_analytics_snapshot",
    "_get_account_content_snapshot",
    "_get_device_follow_feed_snapshot",
    "_get_notifications_snapshot",
    "_handle_twitter_read_error",
    "_normalize_tweet_record",
]
