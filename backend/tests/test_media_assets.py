from __future__ import annotations

from pathlib import Path

import pytest

from hot_backend.media_assets import build_asset_descriptor
from hot_backend.media_variants import normalize_extension
from hot_backend.sqlite_store import HotSQLiteStore


def test_media_asset_urls_follow_static_cloudbase_contract() -> None:
    asset = build_asset_descriptor(
        asset_id="abc123",
        original_ext="png",
    )

    assert asset["original_url"] == "https://static.cloudbase.eu.org/original/abc123.png"
    assert asset["cover_url"] == "https://static.cloudbase.eu.org/cover/abc123.webp"
    assert asset["thumb_url"] == "https://static.cloudbase.eu.org/thumb/abc123.webp"


def test_media_asset_descriptor_normalizes_extension_and_trims_base_url() -> None:
    asset = build_asset_descriptor(
        asset_id="abc123",
        original_ext=".PNG ",
        base_url="https://cdn.example.com///",
    )

    assert asset["original_ext"] == "png"
    assert asset["storage_key_original"] == "original/abc123.png"
    assert asset["original_url"] == "https://cdn.example.com/original/abc123.png"
    assert asset["cover_url"] == "https://cdn.example.com/cover/abc123.webp"
    assert asset["thumb_url"] == "https://cdn.example.com/thumb/abc123.webp"


def test_normalize_extension_rejects_blank_values() -> None:
    with pytest.raises(ValueError, match="original_ext must not be empty"):
        normalize_extension(" . ")


def test_media_asset_row_can_be_persisted_and_loaded(tmp_path: Path) -> None:
    store = HotSQLiteStore(tmp_path / "media-assets.sqlite3")
    store.initialize()

    payload = {
        "asset_id": "abc123",
        "original_ext": "PNG",
        "source_kind": "uploaded",
        "source_origin_url": None,
        "original_url": "https://invalid.example/original/abc123.png",
        "cover_url": "https://invalid.example/cover/abc123.webp",
        "thumb_url": "https://invalid.example/thumb/abc123.webp",
        "storage_key_original": "wrong/original.png",
        "storage_key_cover": "wrong/cover.webp",
        "storage_key_thumb": "wrong/thumb.webp",
        "created_at": "1900-01-01T00:00:00+00:00",
        "updated_at": "1900-01-01T00:00:00+00:00",
    }

    created = store.create_media_asset(payload)

    assert created["asset_id"] == "abc123"
    assert created["source_kind"] == "uploaded"
    assert created["source_origin_url"] is None
    assert created["storage_key_original"] == "original/abc123.png"
    assert created["storage_key_cover"] == "cover/abc123.webp"
    assert created["storage_key_thumb"] == "thumb/abc123.webp"
    assert created["original_url"] == "https://static.cloudbase.eu.org/original/abc123.png"
    assert created["cover_url"] == "https://static.cloudbase.eu.org/cover/abc123.webp"
    assert created["thumb_url"] == "https://static.cloudbase.eu.org/thumb/abc123.webp"
    assert created["created_at"] != "1900-01-01T00:00:00+00:00"
    assert created["updated_at"] != "1900-01-01T00:00:00+00:00"
    assert created["created_at"] == created["updated_at"]

    loaded = store.get_media_asset("abc123")
    assert loaded == created

    listed = store.list_media_assets()
    assert len(listed) == 1
    assert listed[0] == created
