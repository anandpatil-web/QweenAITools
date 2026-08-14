"""Filename helpers.

Two very different concerns:

* **fal upload names** must be safe, generated, ASCII-only names such as
  ``input.jpg``. The user's original filename is *never* sent to fal — names
  like ``Ring Final 01!.jpg`` can trigger "Illegal header value" errors.
* **output/download names** must preserve the user's original filename (with an
  optional suffix and a corrected extension), because that is what the design
  team expects to see when they download.
"""
from __future__ import annotations

import re
from pathlib import Path

# Content-type per canonical extension used for fal uploads.
_EXT_TO_CONTENT_TYPE = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

# fal output_format -> extension for the downloaded/stored result.
_OUTPUT_FORMAT_TO_EXT = {
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "png": ".png",
    "webp": ".webp",
}


def content_type_for_ext(ext: str) -> str:
    return _EXT_TO_CONTENT_TYPE.get(ext.lower(), "application/octet-stream")


def safe_upload_name(canonical_ext: str) -> str:
    """A minimal, safe filename for the fal upload stage."""
    ext = canonical_ext.lower()
    if ext not in _EXT_TO_CONTENT_TYPE:
        ext = ".jpg"
    return f"input{ext}"


def output_extension(output_format: str, fallback_ext: str) -> str:
    return _OUTPUT_FORMAT_TO_EXT.get(output_format.lower(), fallback_ext.lower())


def _sanitize_stem(stem: str) -> str:
    """Make a filename stem safe for a download header / ZIP entry.

    Keeps it readable but strips path separators and control/unsafe characters.
    """
    stem = stem.replace("\x00", "")
    # Drop any path components a malicious name might carry.
    stem = Path(stem).name
    # Remove characters that are unsafe in headers / filesystems / zips.
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
    stem = stem.strip().strip(".")
    stem = re.sub(r"\s+", " ", stem)
    if not stem:
        stem = "image"
    return stem[:200]


def build_output_filename(
    original_filename: str, suffix: str, output_format: str
) -> str:
    """Build the user-facing download filename.

    ``ring.jpg`` + suffix ``_x2`` -> ``ring_x2.jpg``. The extension follows the
    chosen output format so it is always correct.
    """
    original = Path(original_filename).name
    stem = _sanitize_stem(Path(original).stem)
    fallback_ext = Path(original).suffix or ".jpg"
    ext = output_extension(output_format, fallback_ext)
    clean_suffix = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', "_", suffix or "")
    return f"{stem}{clean_suffix}{ext}"
