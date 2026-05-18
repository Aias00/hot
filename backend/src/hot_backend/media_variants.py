from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final


MAX_UPLOAD_SIZE_BYTES: Final[int] = 10 * 1024 * 1024
SUPPORTED_IMAGE_MIME_TYPES: Final[dict[str, str]] = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class MediaUploadValidationError(ValueError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ValidatedImageUpload:
    extension: str
    height: int
    mime_type: str
    size_bytes: int
    width: int


@dataclass(frozen=True, slots=True)
class MediaVariantPlan:
    name: str
    storage_prefix: str
    extension: str
    max_width: int | None = None
    max_height: int | None = None


@dataclass(frozen=True, slots=True)
class PreparedVariantUpload:
    content: bytes
    content_type: str
    height: int
    width: int


def normalize_extension(value: str) -> str:
    normalized = value.strip().lower().lstrip(".")
    if not normalized:
        raise ValueError("original_ext must not be empty")
    return normalized


def _parse_png_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid PNG payload")
    width, height = struct.unpack(">II", content[16:24])
    return width, height


def _parse_gif_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 10 or content[:6] not in {b"GIF87a", b"GIF89a"}:
        raise ValueError("Invalid GIF payload")
    width, height = struct.unpack("<HH", content[6:10])
    return width, height


def _parse_jpeg_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 4 or content[:2] != b"\xff\xd8":
        raise ValueError("Invalid JPEG payload")

    offset = 2
    while offset + 9 < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue

        marker = content[offset + 1]
        offset += 2

        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            break
        if offset + 2 > len(content):
            break

        segment_length = struct.unpack(">H", content[offset : offset + 2])[0]
        if segment_length < 2 or offset + segment_length > len(content):
            break

        if 0xC0 <= marker <= 0xC3 and offset + 7 < len(content):
            height, width = struct.unpack(">HH", content[offset + 3 : offset + 7])
            return width, height

        offset += segment_length

    raise ValueError("JPEG dimensions could not be determined")


def _parse_webp_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 30 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
        raise ValueError("Invalid WebP payload")

    chunk_type = content[12:16]
    if chunk_type == b"VP8X":
        if len(content) < 30:
            raise ValueError("Invalid WebP VP8X payload")
        width = 1 + int.from_bytes(content[24:27], "little")
        height = 1 + int.from_bytes(content[27:30], "little")
        return width, height

    if chunk_type == b"VP8 ":
        if len(content) < 30:
            raise ValueError("Invalid WebP VP8 payload")
        width, height = struct.unpack("<HH", content[26:30])
        return width & 0x3FFF, height & 0x3FFF

    if chunk_type == b"VP8L":
        if len(content) < 25:
            raise ValueError("Invalid WebP VP8L payload")
        bits = int.from_bytes(content[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height

    raise ValueError("Unsupported WebP payload")


def sniff_image_details(content: bytes) -> tuple[str, tuple[int, int]]:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", _parse_png_dimensions(content)
    if content.startswith(b"\xff\xd8"):
        return "image/jpeg", _parse_jpeg_dimensions(content)
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", _parse_gif_dimensions(content)
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp", _parse_webp_dimensions(content)
    raise ValueError("Unsupported or invalid image payload")


def validate_image_upload(
    *,
    content: bytes,
    content_type: str | None,
) -> ValidatedImageUpload:
    size_bytes = len(content)
    if size_bytes == 0:
        raise MediaUploadValidationError("Uploaded file is empty", status_code=400)
    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        raise MediaUploadValidationError(
            f"Uploaded file exceeds the {MAX_UPLOAD_SIZE_BYTES} byte limit",
            status_code=413,
        )

    declared_mime_type = (content_type or "").strip().lower()
    if declared_mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        raise MediaUploadValidationError(
            "Unsupported media type. Supported types: image/gif, image/jpeg, image/png, image/webp",
            status_code=415,
        )

    try:
        sniffed_mime_type, (width, height) = sniff_image_details(content)
    except ValueError as exc:
        raise MediaUploadValidationError(str(exc), status_code=400) from exc

    if sniffed_mime_type != declared_mime_type:
        raise MediaUploadValidationError(
            f"Declared media type '{declared_mime_type}' does not match the uploaded image payload",
            status_code=400,
        )

    return ValidatedImageUpload(
        extension=SUPPORTED_IMAGE_MIME_TYPES[sniffed_mime_type],
        height=height,
        mime_type=sniffed_mime_type,
        size_bytes=size_bytes,
        width=width,
    )


def _require_binary(name: str) -> str:
    binary_path = shutil.which(name)
    if binary_path:
        return binary_path
    raise RuntimeError(f"{name} is required to generate media renditions")


def _render_webp_variant(
    *,
    cwebp_path: str,
    ffmpeg_path: str,
    source_bytes: bytes,
    source_extension: str,
    variant: MediaVariantPlan,
) -> PreparedVariantUpload:
    with tempfile.TemporaryDirectory(prefix="hot-media-variant-") as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / f"source.{source_extension}"
        scaled_png_path = temp_path / f"{variant.name}.png"
        output_path = temp_path / f"{variant.name}.webp"
        source_path.write_bytes(source_bytes)

        scale_parts = []
        if variant.max_width is not None:
            scale_parts.append(f"w='min(iw,{variant.max_width})'")
        if variant.max_height is not None:
            scale_parts.append(f"h='min(ih,{variant.max_height})'")
        scale_parts.append("force_original_aspect_ratio=decrease")
        scale_filter = "scale=" + ":".join(scale_parts)

        scale_command = [
            ffmpeg_path,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-vf",
            scale_filter,
            "-frames:v",
            "1",
            str(scaled_png_path),
        ]
        scale_completed = subprocess.run(scale_command, check=False, capture_output=True)
        if scale_completed.returncode != 0:
            stderr = scale_completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"ffmpeg failed while generating the '{variant.name}' rendition: {stderr or 'unknown error'}"
            )

        encode_command = [
            cwebp_path,
            "-quiet",
            "-q",
            "85",
            str(scaled_png_path),
            "-o",
            str(output_path),
        ]
        encode_completed = subprocess.run(encode_command, check=False, capture_output=True)
        if encode_completed.returncode != 0:
            stderr = encode_completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"cwebp failed while generating the '{variant.name}' rendition: {stderr or 'unknown error'}"
            )

        output_bytes = output_path.read_bytes()

    sniffed_mime_type, (width, height) = sniff_image_details(output_bytes)
    if sniffed_mime_type != "image/webp":
        raise RuntimeError(
            f"Generated '{variant.name}' rendition is not WebP (got {sniffed_mime_type})"
        )
    if variant.max_width is not None and width > variant.max_width:
        raise RuntimeError(
            f"Generated '{variant.name}' rendition width {width} exceeds {variant.max_width}"
        )
    if variant.max_height is not None and height > variant.max_height:
        raise RuntimeError(
            f"Generated '{variant.name}' rendition height {height} exceeds {variant.max_height}"
        )
    return PreparedVariantUpload(
        content=output_bytes,
        content_type="image/webp",
        height=height,
        width=width,
    )


def prepare_variant_uploads(
    *,
    original_content: bytes,
    original_extension: str,
    original_mime_type: str,
) -> dict[str, PreparedVariantUpload]:
    ffmpeg_path = _require_binary("ffmpeg")
    cwebp_path = _require_binary("cwebp")
    _, (original_width, original_height) = sniff_image_details(original_content)
    prepared: dict[str, PreparedVariantUpload] = {
        "original": PreparedVariantUpload(
            content=original_content,
            content_type=original_mime_type,
            height=original_height,
            width=original_width,
        )
    }

    for variant in plan_image_variants(original_extension):
        if variant.name == "original":
            continue
        prepared[variant.name] = _render_webp_variant(
            cwebp_path=cwebp_path,
            ffmpeg_path=ffmpeg_path,
            source_bytes=original_content,
            source_extension=normalize_extension(original_extension),
            variant=variant,
        )

    return prepared


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
