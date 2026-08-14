"""Upscaler tool service — the scan/estimate flow.

The scan step is the cost gate: it validates images, reads their real
dimensions with Pillow, computes the authoritative cost, and persists the
input bytes to disk so processing never re-uploads from the browser. It must
**never** call fal.ai.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import UploadFile

from ...config import (
    ALLOWED_OUTPUT_FORMATS,
    SUPPORTED_SCALE_FACTORS,
    settings,
)
from ...core.logging import get_logger
from ...jobs.manager import Scan, ScanImage, manager
from ...storage import local as storage
from .cost import calculate_cost, usd_to_inr
from .models import ScannedImage, ScanError, ScanResponse
from .validation import ImageValidationError, validate_image

log = get_logger("qween.upscaler")


@dataclass
class ScanInputs:
    scale_factor: int
    output_suffix: str
    output_format: str


def normalise_scale_factor(raw: int | str | None) -> int:
    try:
        value = int(raw) if raw is not None else 2
    except (TypeError, ValueError):
        value = 2
    if value not in SUPPORTED_SCALE_FACTORS:
        value = 2
    return value


def normalise_output_format(raw: str | None) -> str:
    value = (raw or "jpeg").lower().strip()
    if value == "jpg":
        value = "jpeg"
    if value not in ALLOWED_OUTPUT_FORMATS:
        value = "jpeg"
    return value


def normalise_suffix(raw: str | None) -> str:
    return (raw or "").strip()


async def scan_images(
    files: list[UploadFile], inputs: ScanInputs
) -> ScanResponse:
    """Validate + estimate a batch of uploaded images."""
    scan_id = manager.new_scan_id()
    storage.ensure_root()
    inputs_dir = storage.inputs_dir(scan_id)  # noqa: F841 - ensures dir exists

    scanned: list[ScannedImage] = []
    errors: list[ScanError] = []
    scan_images: list[ScanImage] = []

    total_input_mp = 0.0
    total_output_mp = 0.0
    total_cost_usd = 0.0

    for upload in files:
        filename = upload.filename or "image"
        try:
            data = await upload.read()
        except Exception as exc:  # noqa: BLE001
            log.warning("read upload failed filename=%r: %s", filename, exc)
            errors.append(ScanError(filename=filename, error="This image couldn't be read."))
            continue
        finally:
            await upload.close()

        try:
            validated = validate_image(filename, upload.content_type, data)
        except ImageValidationError as exc:
            errors.append(ScanError(filename=filename, error=exc.message))
            continue

        breakdown = calculate_cost(
            validated.width, validated.height, inputs.scale_factor
        )

        image_id = manager.new_image_id()
        input_path = storage.input_path(scan_id, image_id, validated.canonical_ext)
        try:
            input_path.write_bytes(data)
        except OSError as exc:
            log.error("failed to persist input filename=%r: %s", filename, exc)
            errors.append(
                ScanError(filename=filename, error="This image couldn't be stored.")
            )
            continue

        scanned.append(
            ScannedImage(
                id=image_id,
                filename=filename,
                width=validated.width,
                height=validated.height,
                input_megapixels=breakdown.input_megapixels,
                output_width=breakdown.output_width,
                output_height=breakdown.output_height,
                output_megapixels=breakdown.output_megapixels,
                estimated_cost_usd=breakdown.estimated_cost_usd,
                estimated_cost_inr=usd_to_inr(breakdown.estimated_cost_usd),
            )
        )
        scan_images.append(
            ScanImage(
                id=image_id,
                filename=filename,
                ext=validated.canonical_ext,
                width=validated.width,
                height=validated.height,
                output_width=breakdown.output_width,
                output_height=breakdown.output_height,
                input_megapixels=breakdown.input_megapixels,
                output_megapixels=breakdown.output_megapixels,
                estimated_cost_usd=breakdown.estimated_cost_usd,
                input_path=input_path,
            )
        )

        total_input_mp += breakdown.input_megapixels
        total_output_mp += breakdown.output_megapixels
        total_cost_usd += breakdown.estimated_cost_usd

    # Register the scan so a subsequent confirmed job can reuse the inputs.
    if scan_images:
        manager.register_scan(
            Scan(
                id=scan_id,
                scale_factor=inputs.scale_factor,
                output_suffix=inputs.output_suffix,
                output_format=inputs.output_format,
                images=scan_images,
            )
        )
    else:
        # Nothing usable — clean up the empty scan directory.
        storage.delete_job(scan_id)

    total_cost_usd = round(total_cost_usd, 4)
    return ScanResponse(
        scan_id=scan_id,
        scale_factor=inputs.scale_factor,
        output_suffix=inputs.output_suffix,
        output_format=inputs.output_format,
        images=scanned,
        errors=errors,
        total_images=len(scanned),
        total_input_megapixels=round(total_input_mp, 2),
        total_output_megapixels=round(total_output_mp, 2),
        total_cost_usd=total_cost_usd,
        total_cost_inr=usd_to_inr(total_cost_usd),
    )


def clamp_concurrency(requested: int | None) -> int:
    default = min(4, settings.max_concurrency)
    if requested is None:
        requested = default
    try:
        requested = int(requested)
    except (TypeError, ValueError):
        requested = default
    return max(1, min(requested, settings.max_concurrency, 8))
