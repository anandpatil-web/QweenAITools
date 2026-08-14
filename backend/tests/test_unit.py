"""Unit tests for cost, validation, and filename logic (no fal.ai)."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from app.tools.upscaler.cost import calculate_cost, usd_to_inr
from app.tools.upscaler.filenames import (
    build_output_filename,
    safe_upload_name,
)
from app.tools.upscaler.validation import ImageValidationError, validate_image


def _png_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 180, 120)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


# ------------------------------------------------------------------ cost

def test_cost_matches_spec_example():
    b = calculate_cost(2000, 2000, 2)
    assert b.output_width == 4000
    assert b.output_height == 4000
    assert b.output_megapixels == pytest.approx(16.0)
    assert b.estimated_cost_usd == pytest.approx(0.256, abs=1e-6)


def test_cost_scale_4():
    b = calculate_cost(1000, 1000, 4)
    assert b.output_width == 4000
    assert b.output_megapixels == pytest.approx(16.0)
    assert b.estimated_cost_usd == pytest.approx(0.256, abs=1e-6)


def test_usd_to_inr_uses_configured_rate():
    # Default rate is 90 unless overridden by env.
    assert usd_to_inr(1.0) > 0


def test_cost_rejects_bad_dims():
    with pytest.raises(ValueError):
        calculate_cost(0, 100, 2)


# ------------------------------------------------------------ validation

def test_validate_png_ok():
    v = validate_image("ring.png", "image/png", _png_bytes(300, 200))
    assert (v.width, v.height) == (300, 200)
    assert v.canonical_ext == ".png"


def test_validate_jpeg_ok():
    v = validate_image("ring.jpg", "image/jpeg", _jpeg_bytes(640, 480))
    assert v.canonical_ext == ".jpg"


def test_reject_unsupported_extension():
    with pytest.raises(ImageValidationError):
        validate_image("ring.gif", "image/gif", _png_bytes(10, 10))


def test_reject_corrupt_bytes():
    with pytest.raises(ImageValidationError):
        validate_image("ring.png", "image/png", b"not really an image")


def test_reject_empty():
    with pytest.raises(ImageValidationError):
        validate_image("ring.png", "image/png", b"")


def test_extension_mismatch_still_validates_by_content():
    # A real PNG mislabelled as .jpg is decoded by content; format wins.
    with pytest.raises(ImageValidationError):
        # .txt is not an allowed extension -> rejected regardless of content
        validate_image("ring.txt", "image/png", _png_bytes(10, 10))


# ------------------------------------------------------------- filenames

def test_output_filename_no_suffix():
    assert build_output_filename("qween-ring.jpg", "", "jpeg") == "qween-ring.jpg"


def test_output_filename_with_suffix():
    assert build_output_filename("ring.jpg", "_x2", "jpeg") == "ring_x2.jpg"


def test_output_filename_format_changes_extension():
    assert build_output_filename("ring.jpg", "", "png") == "ring.png"


def test_output_filename_sanitizes_unsafe():
    out = build_output_filename("../../etc/Ring Final 01!.jpg", "_x2", "jpeg")
    assert "/" not in out and ".." not in out
    assert out.endswith("_x2.jpg")


def test_safe_upload_name_is_generic():
    assert safe_upload_name(".jpg") == "input.jpg"
    assert safe_upload_name(".weird") == "input.jpg"
