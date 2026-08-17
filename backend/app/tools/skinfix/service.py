"""Skin Fix service — validate, prepare image/mask, call OpenAI, store result.

Skin Fix is a single-image, synchronous operation (no batch/job/SSE). The
working image and the optional mask are normalised to the same target size so
OpenAI's edit call, the mask, and the output all align. The result is written
to temp storage and referenced by an opaque ``result_id``.
"""
from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path

from PIL import Image

from ...core.logging import get_logger
from ...providers.openai import get_openai_provider
from ...storage import local as storage
from ..upscaler.filenames import build_output_filename
from ..upscaler.validation import ImageValidationError, validate_image
from .models import SkinFixMode, SkinFixResult, SkinFixStrength
from .prompts import build_skinfix_prompt

log = get_logger("qween.skinfix")

_MAX_EDGE = 2048

# result_id -> stored PNG path (files auto-expire via storage.cleanup_expired).
_results: dict[str, Path] = {}


def _new_result_id() -> str:
    return f"skr_{uuid.uuid4().hex[:12]}"


def compute_output_size(nat_w: int, nat_h: int) -> tuple[int, int]:
    """Native-size output: max 2048 edge, multiple of 16, aspect <= 3:1."""
    w = float(nat_w)
    h = float(nat_h)
    if max(w, h) > _MAX_EDGE:
        s = _MAX_EDGE / max(w, h)
        w *= s
        h *= s
    ar = max(w / h, h / w)
    if ar > 3:
        if w > h:
            h = w / 3
        else:
            w = h / 3
    ow = max(16, round(w / 16) * 16)
    oh = max(16, round(h / 16) * 16)
    return int(ow), int(oh)


def resolve_result(result_id: str) -> Path | None:
    path = _results.get(result_id)
    if path and path.exists():
        return path
    return None


async def run_skin_fix(
    *,
    filename: str,
    content_type: str | None,
    image_data: bytes,
    mask_data: bytes | None,
    mode: SkinFixMode,
    strength: SkinFixStrength,
) -> SkinFixResult:
    """Validate inputs, call OpenAI, persist the result, return its metadata."""
    validated = validate_image(filename, content_type, image_data)

    target_w, target_h = compute_output_size(validated.width, validated.height)
    size = f"{target_w}x{target_h}"

    # Normalise the working image to the target size (RGBA PNG).
    prepared_image = _to_png(image_data, (target_w, target_h))

    prepared_mask: bytes | None = None
    if mode is SkinFixMode.MASKED:
        if not mask_data:
            raise ImageValidationError(
                "No brushed area was provided. Paint over the skin to fix, or "
                "switch to full-image fix."
            )
        prepared_mask = _prepare_mask(mask_data, (target_w, target_h))

    prompt = build_skinfix_prompt(mode, strength)

    provider = get_openai_provider()
    result = await provider.edit_image(
        image_bytes=prepared_image,
        image_filename="image.png",
        image_content_type="image/png",
        prompt=prompt,
        size=size,
        mask_bytes=prepared_mask,
    )

    # Persist output and read its real dimensions.
    result_id = _new_result_id()
    out_path = storage.output_path(result_id, "skinfix", ".png")
    out_path.write_bytes(result.image_bytes)
    _results[result_id] = out_path

    with Image.open(io.BytesIO(result.image_bytes)) as img:
        out_w, out_h = img.size

    output_filename = build_output_filename(filename, "_skinfix", "png")
    data_url = "data:image/png;base64," + base64.b64encode(result.image_bytes).decode()
    log.info(
        "skinfix done result_id=%s mode=%s strength=%s size=%s out=%dx%d",
        result_id,
        mode.value,
        strength.value,
        size,
        out_w,
        out_h,
    )
    return SkinFixResult(
        result_id=result_id,
        output_filename=output_filename,
        width=out_w,
        height=out_h,
        size=size,
        mode=mode,
        strength=strength,
        image_data_url=data_url,
    )


def _to_png(data: bytes, target: tuple[int, int]) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        if img.size != target:
            img = img.resize(target, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def _prepare_mask(data: bytes, target: tuple[int, int]) -> bytes:
    """Ensure the mask is an RGBA PNG at the target size.

    Transparent pixels mark the editable region (OpenAI convention); this
    matches the frontend mask (opaque base, brushed area punched to transparent).
    """
    try:
        with Image.open(io.BytesIO(data)) as mask:
            mask = mask.convert("RGBA")
            if mask.size != target:
                mask = mask.resize(target, Image.LANCZOS)
            buf = io.BytesIO()
            mask.save(buf, format="PNG")
            return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        raise ImageValidationError("The brushed mask could not be read.") from exc


def make_preview(path: Path, max_edge: int = 1600, quality: int = 82) -> bytes:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
