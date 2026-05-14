from __future__ import annotations

from hot_backend.collectors.models import SourceAdapter


class SourceAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters[adapter.adapter_kind] = adapter

    def get(self, adapter_kind: str) -> SourceAdapter:
        if adapter_kind not in self._adapters:
            raise KeyError(f"unknown adapter kind: {adapter_kind}")
        return self._adapters[adapter_kind]

    def list_registered(self) -> list[str]:
        return sorted(self._adapters.keys())
