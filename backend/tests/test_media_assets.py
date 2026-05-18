from __future__ import annotations

from pathlib import Path

from hot_backend.media_assets import build_asset_descriptor
from hot_backend.sqlite_store import HotSQLiteStore


def test_media_asset_urls_follow_static_cloudbase_contract() -> None:
    asset = build_asset_descriptor(
        asset_id="abc123",
        original_ext="png",
    )

    assert asset["original_url"] == "https://static.cloudbase.eu.org/original/abc123.png"
    assert asset["cover_url"] == "https://static.cloudbase.eu.org/cover/abc123.webp"
    assert asset["thumb_url"] == "https://static.cloudbase.eu.org/thumb/abc123.webp"


def test_media_asset_row_can_be_persisted_and_loaded(tmp_path: Path) -> None:
    store = HotSQLiteStore(tmp_path / "media-assets.sqlite3")
    store.initialize()

    payload = {
        "asset_id": "abc123",
        "source_kind": "uploaded",
        "source_origin_url": None,
        "storage_key_original": "original/abc123.png",
        "storage_key_cover": "cover/abc123.webp",
        "storage_key_thumb": "thumb/abc123.webp",
    }

    created = store.create_media_asset(payload)

    assert created["asset_id"] == "abc123"
    assert created["source_kind"] == "uploaded"
    assert created["source_origin_url"] is None
    assert created["storage_key_original"] == "original/abc123.png"
    assert created["storage_key_cover"] == "cover/abc123.webp"
    assert created["storage_key_thumb"] == "thumb/abc123.webp"

    loaded = store.get_media_asset("abc123")
    assert loaded == created

    listed = store.list_media_assets()
    assert len(listed) == 1
    assert listed[0] == created
