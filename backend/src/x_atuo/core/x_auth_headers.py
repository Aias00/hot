"""Public header construction helpers for authenticated X requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from x_atuo.core.x_native_constants import BEARER_TOKEN as TWITTER_BEARER_TOKEN  # noqa: F401
from x_atuo.core.x_native_constants import get_user_agent

if TYPE_CHECKING:
    from x_atuo.core.twitter_client import TwitterCredentials


def build_x_headers(
    *,
    credentials: "TwitterCredentials",
    referer: str = "https://x.com/",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}",
        "Cookie": f"auth_token={credentials.auth_token}; ct0={credentials.ct0}",
        "X-Csrf-Token": credentials.ct0,
        "X-Twitter-Active-User": "yes",
        "X-Twitter-Auth-Type": "OAuth2Session",
        "X-Twitter-Client-Language": "en",
        "User-Agent": get_user_agent(),
        "Origin": "https://x.com",
        "Referer": referer,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    if extra:
        headers.update(extra)
    return headers
