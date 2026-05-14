"""Shared cookie-authenticated X Web transport primitives."""

from __future__ import annotations

import json
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from x_atuo.core.twitter_client import TwitterCredentials
from x_atuo.core import x_auth_headers


class XWebTransportError(RuntimeError):
    """Raised when shared X Web transport fails."""


class XWebTransport:
    def __init__(
        self,
        *,
        credentials: TwitterCredentials,
        proxy: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.credentials = credentials
        self.proxy = proxy
        self.timeout_seconds = timeout_seconds

    def build_headers(self, *, referer: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        return x_auth_headers.build_x_headers(
            credentials=self.credentials,
            referer=referer,
            extra=extra,
        )

    def get_json(
        self,
        url: str,
        *,
        referer: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        headers = self.build_headers(referer=referer, extra=extra_headers)
        request = Request(url, headers=headers, method="GET")
        if self.proxy:
            opener = build_opener(ProxyHandler({"http": self.proxy, "https": self.proxy}))
            response = opener.open(request, timeout=self.timeout_seconds)
        else:
            response = urlopen(request, timeout=self.timeout_seconds)
        with response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise XWebTransportError(f"unexpected X Web payload type: {type(payload)!r}")
        return payload
