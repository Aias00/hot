from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MediaVariantPlan:
    name: str
    storage_prefix: str
    extension: str
    max_width: int | None = None
    max_height: int | None = None


def normalize_extension(value: str) -> str:
    normalized = value.strip().lower().lstrip(".")
    if not normalized:
        raise ValueError("original_ext must not be empty")
    return normalized


def plan_image_variants(original_ext: str) -> tuple[MediaVariantPlan, ...]:
    normalized_ext = normalize_extension(original_ext)
    return (
        MediaVariantPlan(
            name="original",
            storage_prefix="original",
            extension=normalized_ext,
        ),
        MediaVariantPlan(
            name="cover",
            storage_prefix="cover",
            extension="webp",
            max_width=1600,
            max_height=1600,
        ),
        MediaVariantPlan(
            name="thumb",
            storage_prefix="thumb",
            extension="webp",
            max_width=480,
            max_height=480,
        ),
    )
