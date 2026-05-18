from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from curl_cffi import requests

from hot_backend.media_variants import (
    MediaUploadValidationError,
    normalize_extension,
    plan_image_variants,
    prepare_variant_uploads,
    validate_image_upload,
)


DEFAULT_MEDIA_CDN_BASE_URL = "https://static.cloudbase.eu.org"
R2_SERVICE = "s3"
R2_REGION = "auto"


@dataclass(frozen=True, slots=True)
class R2Config:
    access_key_id: str
    account_id: str
    bucket: str
    secret_access_key: str


def get_media_cdn_base_url() -> str:
    return os.environ.get("MEDIA_CDN_BASE_URL", DEFAULT_MEDIA_CDN_BASE_URL)


def build_public_urls(
    asset_id: str,
    original_ext: str,
    base_url: str | None = None,
) -> dict[str, str]:
    normalized_ext = normalize_extension(original_ext)
    base = (base_url or get_media_cdn_base_url()).rstrip("/")
    return {
        "original_url": f"{base}/original/{asset_id}.{normalized_ext}",
        "cover_url": f"{base}/cover/{asset_id}.webp",
        "thumb_url": f"{base}/thumb/{asset_id}.webp",
    }


def build_asset_descriptor(
    asset_id: str,
    original_ext: str,
    base_url: str | None = None,
) -> dict[str, str]:
    urls = build_public_urls(asset_id=asset_id, original_ext=original_ext, base_url=base_url)
    storage_keys = {
        f"storage_key_{variant.name}": (
            f"{variant.storage_prefix}/{asset_id}.{variant.extension}"
        )
        for variant in plan_image_variants(original_ext)
    }
    return {
        "asset_id": asset_id,
        "original_ext": normalize_extension(original_ext),
        **storage_keys,
        **urls,
    }


def _get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} environment variable is required for media uploads")
    return value


def get_r2_config() -> R2Config:
    return R2Config(
        access_key_id=_get_required_env("R2_ACCESS_KEY_ID"),
        account_id=_get_required_env("R2_ACCOUNT_ID"),
        bucket=_get_required_env("R2_BUCKET"),
        secret_access_key=_get_required_env("R2_SECRET_ACCESS_KEY"),
    )


def _build_r2_request(
    *,
    config: R2Config,
    content: bytes,
    content_type: str | None,
    method: str,
    storage_key: str,
) -> tuple[str, dict[str, str]]:
    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    quoted_storage_key = quote(storage_key, safe="/-_.~")
    canonical_uri = f"/{config.bucket}/{quoted_storage_key}"
    host = f"{config.account_id}.r2.cloudflarestorage.com"
    payload_hash = hashlib.sha256(content).hexdigest()
    canonical_headers_parts = [f"host:{host}", f"x-amz-content-sha256:{payload_hash}", f"x-amz-date:{amz_date}"]
    signed_header_names = ["host", "x-amz-content-sha256", "x-amz-date"]
    if content_type:
        canonical_headers_parts.insert(0, f"content-type:{content_type}")
        signed_header_names.insert(0, "content-type")
    canonical_headers = "\n".join(canonical_headers_parts) + "\n"
    signed_headers = ";".join(signed_header_names)
    canonical_request = "\n".join(
        (
            method,
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        )
    )
    credential_scope = f"{date_stamp}/{R2_REGION}/{R2_SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        (
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        )
    )
    signing_key = _derive_signature_key(
        secret_access_key=config.secret_access_key,
        date_stamp=date_stamp,
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={config.access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    return (
        f"https://{host}{canonical_uri}",
        {
            "Authorization": authorization,
            "Host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            **({"Content-Type": content_type} if content_type else {}),
        },
    )


def _derive_signature_key(*, secret_access_key: str, date_stamp: str) -> bytes:
    k_date = hmac.new(
        f"AWS4{secret_access_key}".encode("utf-8"),
        date_stamp.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    k_region = hmac.new(k_date, R2_REGION.encode("utf-8"), hashlib.sha256).digest()
    k_service = hmac.new(k_region, R2_SERVICE.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()


def _cleanup_uploaded_objects(uploaded_storage_keys: list[str]) -> None:
    for storage_key in uploaded_storage_keys:
        try:
            delete_from_r2(storage_key=storage_key)
        except RuntimeError:
            continue


def upload_to_r2(*, storage_key: str, content: bytes, content_type: str) -> None:
    config = get_r2_config()
    url, headers = _build_r2_request(
        config=config,
        content=content,
        content_type=content_type,
        method="PUT",
        storage_key=storage_key,
    )
    try:
        response = requests.put(url, data=content, headers=headers, timeout=30)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError("Media storage upload is temporarily unavailable") from exc
    if response.status_code not in {200, 201, 204}:
        raise RuntimeError("Media storage upload is temporarily unavailable")


def delete_from_r2(*, storage_key: str) -> None:
    config = get_r2_config()
    url, headers = _build_r2_request(
        config=config,
        content=b"",
        content_type=None,
        method="DELETE",
        storage_key=storage_key,
    )
    try:
        response = requests.delete(url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError("Media storage cleanup is temporarily unavailable") from exc
    if response.status_code not in {200, 204, 404}:
        raise RuntimeError("Media storage cleanup is temporarily unavailable")


def create_uploaded_media_asset(
    *,
    content: bytes,
    content_type: str | None,
    store: Any,
) -> dict[str, Any]:
    validated = validate_image_upload(content=content, content_type=content_type)
    asset_id = secrets.token_hex(12)
    descriptor = build_asset_descriptor(
        asset_id=asset_id,
        original_ext=validated.extension,
    )

    prepared_uploads = prepare_variant_uploads(
        original_content=content,
        original_extension=validated.extension,
        original_mime_type=validated.mime_type,
    )

    uploaded_storage_keys: list[str] = []
    try:
        for variant in plan_image_variants(validated.extension):
            storage_key = descriptor[f"storage_key_{variant.name}"]
            prepared = prepared_uploads[variant.name]
            upload_to_r2(
                storage_key=storage_key,
                content=prepared.content,
                content_type=prepared.content_type,
            )
            uploaded_storage_keys.append(storage_key)

        return store.create_media_asset(
            {
                "asset_id": asset_id,
                "content_hash": hashlib.sha256(content).hexdigest(),
                "height": validated.height,
                "mime_type": validated.mime_type,
                "original_ext": validated.extension,
                "source_kind": "uploaded",
                "source_origin_url": None,
                "status": "ready",
                "width": validated.width,
            }
        )
    except Exception:
        _cleanup_uploaded_objects(uploaded_storage_keys)
        raise
