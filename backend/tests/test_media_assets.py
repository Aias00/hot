from __future__ import annotations

from base64 import b64decode
from pathlib import Path
import struct
import zlib

import pytest
from curl_cffi import requests as curl_requests
from fastapi.testclient import TestClient

from hot_backend.app import create_app
from hot_backend.auth import TokenPayload, get_current_admin
from hot_backend.media_assets import build_asset_descriptor, create_uploaded_media_asset
from hot_backend.media_variants import PreparedVariantUpload, normalize_extension, sniff_image_details
from hot_backend.sqlite_store import HotSQLiteStore

MAX_TEST_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
PNG_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmZ0AAAAASUVORK5CYII="
)


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )


def _make_png_bytes(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
    )
    row = b"\x00" + (b"\x33\x99\xcc" * width)
    raw = row * height
    idat = _png_chunk(b"IDAT", zlib.compress(raw))
    iend = _png_chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def _make_corrupt_png_bytes(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
    )
    invalid_idat = _png_chunk(b"IDAT", b"not-a-valid-zlib-stream")
    iend = _png_chunk(b"IEND", b"")
    return signature + ihdr + invalid_idat + iend


def _create_admin_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, HotSQLiteStore]:
    store = HotSQLiteStore(tmp_path / "media-assets.sqlite3")
    store.initialize()
    monkeypatch.setattr("hot_backend.sqlite_store.get_store", lambda: store)

    app = create_app()
    app.dependency_overrides[get_current_admin] = lambda: TokenPayload(
        sub="admin",
        iat=0,
        exp=4102444800,
    )
    return TestClient(app), store


def _create_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, HotSQLiteStore]:
    store = HotSQLiteStore(tmp_path / "media-assets.sqlite3")
    store.initialize()
    monkeypatch.setattr("hot_backend.sqlite_store.get_store", lambda: store)
    return TestClient(create_app()), store


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


def test_admin_media_upload_returns_asset_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploads: list[tuple[str, str, bytes]] = []
    upload_bytes = _make_png_bytes(640, 320)

    def fake_upload_to_r2(*, storage_key: str, content: bytes, content_type: str) -> None:
        uploads.append((storage_key, content_type, content))

    client, store = _create_admin_client(tmp_path, monkeypatch)
    monkeypatch.setattr("hot_backend.media_assets.upload_to_r2", fake_upload_to_r2)

    response = client.post(
        "/api/admin/media-assets/upload",
        files={"file": ("qr.png", upload_bytes, "image/png")},
    )

    assert response.status_code == 201
    body = response.json()

    assert body["asset_id"]
    assert body["source_kind"] == "uploaded"
    assert body["original_url"].startswith("https://static.cloudbase.eu.org/")
    assert body["cover_url"].startswith("https://static.cloudbase.eu.org/")
    assert body["thumb_url"].startswith("https://static.cloudbase.eu.org/")
    assert body["width"] == 640
    assert body["height"] == 320
    assert body["mime_type"] == "image/png"
    assert body["status"] == "ready"

    assert len(uploads) == 3

    original_upload = uploads[0]
    cover_upload = uploads[1]
    thumb_upload = uploads[2]

    assert original_upload == (body["storage_key_original"], "image/png", upload_bytes)
    assert cover_upload[0] == body["storage_key_cover"]
    assert cover_upload[1] == "image/webp"
    assert cover_upload[2] != upload_bytes
    assert sniff_image_details(cover_upload[2]) == ("image/webp", (640, 320))

    assert thumb_upload[0] == body["storage_key_thumb"]
    assert thumb_upload[1] == "image/webp"
    assert thumb_upload[2] != upload_bytes
    assert thumb_upload[2] != cover_upload[2]
    assert sniff_image_details(thumb_upload[2]) == ("image/webp", (480, 240))

    assert store.get_media_asset(body["asset_id"]) == body


def test_admin_media_upload_rejects_oversized_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _create_admin_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/admin/media-assets/upload",
        files={
            "file": (
                "qr.png",
                PNG_BYTES + (b"\x00" * MAX_TEST_UPLOAD_SIZE_BYTES),
                "image/png",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Uploaded file exceeds the 10485760 byte limit"


def test_admin_about_put_requires_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _create_client(tmp_path, monkeypatch)

    response = client.put(
        "/api/admin/about",
        json={
            "title": "关于我们",
            "description": "desc",
            "qr_code_url": "https://static.cloudbase.eu.org/original/asset-123.png",
            "follow_link": "",
            "contact_info": "",
            "links": [],
        },
    )

    assert response.status_code == 401


def test_admin_about_put_persists_config_for_authenticated_admin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, store = _create_admin_client(tmp_path, monkeypatch)

    response = client.put(
        "/api/admin/about",
        json={
            "title": "关于我们",
            "description": "desc",
            "qr_code_url": "https://static.cloudbase.eu.org/original/asset-123.png",
            "follow_link": "https://example.com/follow",
            "contact_info": "wechat: cloudbase",
            "links": [{"label": "官网", "url": "https://example.com"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": "关于我们",
        "description": "desc",
        "qr_code_url": "https://static.cloudbase.eu.org/original/asset-123.png",
        "follow_link": "https://example.com/follow",
        "contact_info": "wechat: cloudbase",
        "links": [{"label": "官网", "url": "https://example.com"}],
    }
    assert store.get_about_config() == response.json()


def test_admin_media_upload_maps_r2_request_exception_to_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _create_admin_client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "hot_backend.media_assets.prepare_variant_uploads",
        lambda **_: {
            "original": PreparedVariantUpload(
                content=PNG_BYTES,
                content_type="image/png",
                width=1,
                height=1,
            ),
            "cover": PreparedVariantUpload(
                content=b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0c\x00\x00\x000\x01\x00\x9d\x01*\x01\x00\x01\x00\x00\x00",
                content_type="image/webp",
                width=1,
                height=1,
            ),
            "thumb": PreparedVariantUpload(
                content=b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0c\x00\x00\x000\x01\x00\x9d\x01*\x01\x00\x01\x00\x00\x00",
                content_type="image/webp",
                width=1,
                height=1,
            ),
        },
    )
    monkeypatch.setattr(
        "hot_backend.media_assets.get_r2_config",
        lambda: type(
            "DummyR2Config",
            (),
            {
                "access_key_id": "key",
                "account_id": "acct",
                "bucket": "bucket",
                "secret_access_key": "secret",
            },
        )(),
    )

    def raise_timeout(*args, **kwargs):
        raise curl_requests.exceptions.Timeout("network timeout")

    monkeypatch.setattr("hot_backend.media_assets.requests.put", raise_timeout)

    response = client.post(
        "/api/admin/media-assets/upload",
        files={"file": ("qr.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Media storage upload is temporarily unavailable"


def test_admin_media_upload_maps_corrupt_decode_failure_to_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _create_admin_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/admin/media-assets/upload",
        files={"file": ("broken.png", _make_corrupt_png_bytes(64, 64), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded image could not be decoded into required renditions"


def test_uploaded_media_asset_cleans_up_on_later_upload_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploaded: list[str] = []
    deleted: list[str] = []
    store = HotSQLiteStore(Path("/tmp/unused-media-assets.sqlite3"))

    monkeypatch.setattr(
        "hot_backend.media_assets.prepare_variant_uploads",
        lambda **_: {
            "original": PreparedVariantUpload(
                content=PNG_BYTES,
                content_type="image/png",
                width=1,
                height=1,
            ),
            "cover": PreparedVariantUpload(
                content=b"cover-bytes",
                content_type="image/webp",
                width=1,
                height=1,
            ),
            "thumb": PreparedVariantUpload(
                content=b"thumb-bytes",
                content_type="image/webp",
                width=1,
                height=1,
            ),
        },
    )

    def fake_upload_to_r2(*, storage_key: str, content: bytes, content_type: str) -> None:
        uploaded.append(storage_key)
        if storage_key.startswith("cover/"):
            raise RuntimeError("Media storage upload is temporarily unavailable")

    def fake_delete_from_r2(*, storage_key: str) -> None:
        deleted.append(storage_key)

    monkeypatch.setattr("hot_backend.media_assets.upload_to_r2", fake_upload_to_r2)
    monkeypatch.setattr("hot_backend.media_assets.delete_from_r2", fake_delete_from_r2)

    with pytest.raises(RuntimeError, match="Media storage upload is temporarily unavailable"):
        create_uploaded_media_asset(
            content=PNG_BYTES,
            content_type="image/png",
            store=store,
        )

    assert uploaded[0].startswith("original/")
    assert uploaded[1].startswith("cover/")
    assert deleted == [uploaded[0]]


def test_uploaded_media_asset_cleans_up_when_db_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploaded: list[str] = []
    deleted: list[str] = []

    class FailingStore:
        def create_media_asset(self, asset: dict) -> dict:
            raise RuntimeError("database write failed")

    monkeypatch.setattr(
        "hot_backend.media_assets.prepare_variant_uploads",
        lambda **_: {
            "original": PreparedVariantUpload(
                content=PNG_BYTES,
                content_type="image/png",
                width=1,
                height=1,
            ),
            "cover": PreparedVariantUpload(
                content=b"cover-bytes",
                content_type="image/webp",
                width=1,
                height=1,
            ),
            "thumb": PreparedVariantUpload(
                content=b"thumb-bytes",
                content_type="image/webp",
                width=1,
                height=1,
            ),
        },
    )
    monkeypatch.setattr(
        "hot_backend.media_assets.upload_to_r2",
        lambda *, storage_key, content, content_type: uploaded.append(storage_key),
    )
    monkeypatch.setattr(
        "hot_backend.media_assets.delete_from_r2",
        lambda *, storage_key: deleted.append(storage_key),
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        create_uploaded_media_asset(
            content=PNG_BYTES,
            content_type="image/png",
            store=FailingStore(),
        )

    assert deleted == uploaded
