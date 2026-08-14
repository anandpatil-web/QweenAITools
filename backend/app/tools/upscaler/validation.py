"""Image validation using Pillow.

Every uploaded image is validated before it is ever sent to fal.ai:

* extension is one of the accepted image types
* declared MIME type is acceptable
* file size is within the configured limit
* the bytes actually decode as an image (Pillow ``verify`` + real load)
* dimensions can be read

Validation failures raise :class:`ImageValidationError` carrying a
human-readable message that is safe to surface to the user.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ...config import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, settings

# Pillow format name -> canonical extension for stored/output files.
_PIL_FORMAT_TO_EXT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "MPO": ".jpg",  # multi-picture JPEG (some cameras) — treat as JPEG
}


class ImageValidationError(Exception):
    """Raised when an uploaded file is not an acceptable image."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ValidatedImage:
    width: int
    height: int
    pil_format: str
    canonical_ext: str


def _extension_of(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_image(filename: str, content_type: str | None, data: bytes) -> ValidatedImage:
    """Validate raw upload bytes. Returns image facts or raises.

    ``filename`` and ``content_type`` come from the client and are treated as
    untrusted hints; the authoritative check is decoding the bytes with Pillow.
    """
    if not data:
        raise ImageValidationError("This image is empty.")

    if len(data) > settings.max_file_size_bytes:
        raise ImageValidationError(
            f"This image is larger than the {settings.max_file_size_mb} MB limit."
        )

    ext = _extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(
            "Unsupported image format. Please use JPG, JPEG, PNG, or WEBP."
        )

    # content_type is a hint; reject only if it is clearly a non-image type.
    if content_type:
        normalised = content_type.split(";")[0].strip().lower()
        if normalised and not normalised.startswith("image/"):
            raise ImageValidationError(
                "Unsupported image format. Please use JPG, JPEG, PNG, or WEBP."
            )
        if normalised and normalised not in ALLOWED_MIME_TYPES:
            # Some browsers send image/jpg for .jpg — tolerate common variants.
            if normalised not in {"image/jpg", "image/pjpeg", "image/x-png"}:
                raise ImageValidationError(
                    "Unsupported image format. Please use JPG, JPEG, PNG, or WEBP."
                )

    # verify() then a fresh load(): verify() invalidates the object so we must
    # re-open to actually read pixels and dimensions.
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ImageValidationError(
            "This image could not be read. It may be corrupted or invalid."
        )

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            width, height = img.size
            pil_format = (img.format or "").upper()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ImageValidationError(
            "This image could not be read. It may be corrupted or invalid."
        )

    if width <= 0 or height <= 0:
        raise ImageValidationError(
            "This image could not be read. It may be corrupted or invalid."
        )

    if pil_format not in _PIL_FORMAT_TO_EXT:
        raise ImageValidationError(
            "Unsupported image format. Please use JPG, JPEG, PNG, or WEBP."
        )

    return ValidatedImage(
        width=width,
        height=height,
        pil_format=pil_format,
        canonical_ext=_PIL_FORMAT_TO_EXT[pil_format],
    )
