"""Shared async/datetime/error-detection utilities for automation workflows."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from x_atuo.automation.state import FeedCandidate


def utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


async def maybe_await(value: Any) -> Any:
    """Await value if it is a coroutine or future, otherwise return as-is."""
    if inspect.isawaitable(value):
        return await value
    return value


def parse_created_at_with_original_timezone(value: Any) -> datetime | None:
    """Parse a tweet created_at value, preserving the original timezone.

    Accepts an ISO-8601 string, an RFC-2822 string (Twitter API format),
    or an already-parsed datetime. Returns None if the value cannot be
    parsed or has no timezone information.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else None
    except (TypeError, ValueError, IndexError):
        return None


# ── Transient error detection ────────────────────────────────────────────

_TRANSIENT_AI_MARKERS = (
    "timed out",
    "timeout",
    "read operation timed out",
    "http error 500",
    "internal server error",
)

_TRANSIENT_NETWORK_MARKERS = (
    "timed out",
    "timeout",
    "tls connect error",
    "curl: (35)",
    "curl: (28)",
    "ssl",
    "unexpected eof",
    "eof occurred",
    "remote end closed connection",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
)


def is_transient_ai_error(message: str) -> bool:
    """Return True if the message indicates a transient AI provider failure."""
    normalized = message.strip().lower()
    return any(marker in normalized for marker in _TRANSIENT_AI_MARKERS)


def is_transient_network_error(message: str) -> bool:
    """Return True if the message indicates a transient network-level failure."""
    normalized = message.strip().lower()
    return any(marker in normalized for marker in _TRANSIENT_NETWORK_MARKERS)


# ── Timestamp helpers ────────────────────────────────────────────────────────

def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 or Z-suffixed timestamp string to a UTC-aware datetime."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def normalize_timestamp(value: str) -> str:
    """Return the UTC ISO-8601 string for the given timestamp."""
    return parse_timestamp(value).isoformat()


# ── JSON helpers ─────────────────────────────────────────────────────────────

def serialize_json(value: Any) -> str | None:
    """Serialize *value* to a compact JSON string, or None if value is None."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def deserialize_json(value: str | None) -> Any:
    """Deserialize a JSON string, or return None if value is None."""
    if value is None:
        return None
    return json.loads(value)


# ── Candidate helpers ────────────────────────────────────────────────────────

def candidate_current_day_reason(
    candidate: FeedCandidate, *, now: datetime | None = None
) -> str | None:
    """Return a skip reason if the candidate was not posted today (local time).

    Returns None when the candidate is current-day and should not be skipped.
    *now* defaults to the current UTC wall clock if omitted.
    """
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    raw_created_at = None
    for key in ("created_at", "createdAt", "timestamp", "published_at", "publishedAt"):
        if key in metadata:
            raw_created_at = metadata.get(key)
            break
    created_at = parse_created_at_with_original_timezone(raw_created_at)
    if created_at is None:
        created_at = (
            candidate.created_at
            if isinstance(candidate.created_at, datetime) and candidate.created_at.tzinfo
            else None
        )
    if created_at is None:
        return "tweet created_at missing or invalid"
    anchor = now or datetime.now(UTC)
    anchor = anchor.astimezone(created_at.tzinfo) if created_at.tzinfo else anchor
    if anchor.date() != created_at.date():
        return "tweet not from its local current day"
    return None
