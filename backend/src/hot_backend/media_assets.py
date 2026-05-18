from __future__ import annotations

import os

from hot_backend.media_variants import normalize_extension, plan_image_variants


DEFAULT_MEDIA_CDN_BASE_URL = "https://static.cloudbase.eu.org"


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
