"""HTTP API for the Image Upscaler tool."""
from __future__ import annotations

import asyncio
import io
import json
import zipfile
from collections import defaultdict

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image

from ...config import (
    ALLOWED_CONCURRENCY,
    CRYSTAL_USD_PER_MEGAPIXEL,
    CREATIVITY_DEFAULT,
    CREATIVITY_MAX,
    CREATIVITY_MIN,
    SCALE_FACTOR_DEFAULT,
    SCALE_FACTOR_MAX,
    SCALE_FACTOR_MIN,
    settings,
)
from ...core.logging import get_logger
from ...jobs.manager import ImageJob, Job, manager
from ...jobs.worker import retry_images, start_job_processing
from ...storage import local as storage
from .filenames import content_type_for_ext
from .models import (
    ImageState,
    ImageStatus,
    JobResponse,
    RetryRequest,
    StartJobRequest,
)
from .service import (
    ScanInputs,
    clamp_concurrency,
    normalise_creativity,
    normalise_output_format,
    normalise_scale_factor,
    normalise_suffix,
    scan_images,
)

log = get_logger("qween.api.upscaler")

router = APIRouter(prefix="/api", tags=["upscaler"])

_PREVIEW_MAX_EDGE = 1600
_PREVIEW_QUALITY = 82


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

@router.get("/config")
async def get_config() -> dict:
    """Non-secret configuration the frontend needs. Never includes FAL_KEY.

    Editable defaults (scale, concurrency, suffix, INR rate) come from the
    optional Supabase settings store overlaid on env defaults.
    """
    from ...settings.service import get_effective_settings

    effective = await get_effective_settings()
    return {
        "usd_to_inr": effective["usd_to_inr"],
        "scale_min": SCALE_FACTOR_MIN,
        "scale_max": SCALE_FACTOR_MAX,
        "scale_default": SCALE_FACTOR_DEFAULT,
        "creativity_min": CREATIVITY_MIN,
        "creativity_max": CREATIVITY_MAX,
        "creativity_default": CREATIVITY_DEFAULT,
        "usd_per_megapixel": CRYSTAL_USD_PER_MEGAPIXEL,
        "allowed_concurrency": list(ALLOWED_CONCURRENCY),
        "default_scale_factor": effective["default_scale_factor"],
        "default_concurrency": effective["default_concurrency"],
        "default_suffix": effective["default_suffix"],
        "default_output_format": effective["default_output_format"],
        "max_concurrency": min(settings.max_concurrency, 8),
        "max_file_size_mb": settings.max_file_size_mb,
        "image_timeout_seconds": settings.image_timeout_seconds,
        "output_formats": ["jpeg", "png"],
        "accepted_extensions": ["jpg", "jpeg", "png", "webp"],
        "fal_configured": settings.fal_key_present,
        "supabase_configured": settings.supabase_configured,
    }


# --------------------------------------------------------------------------- #
# Scan & Estimate  (NEVER calls fal.ai)
# --------------------------------------------------------------------------- #

@router.post("/scan")
async def scan(
    images: list[UploadFile] = File(...),
    scale_factor: str = Form("2"),
    creativity: str = Form("0"),
    output_suffix: str = Form(""),
    output_format: str = Form("jpeg"),
) -> JSONResponse:
    if not images:
        raise HTTPException(status_code=400, detail="No images were provided.")

    inputs = ScanInputs(
        scale_factor=normalise_scale_factor(scale_factor),
        creativity=normalise_creativity(creativity),
        output_suffix=normalise_suffix(output_suffix),
        output_format=normalise_output_format(output_format),
    )
    result = await scan_images(images, inputs)
    return JSONResponse(content=result.model_dump())


# --------------------------------------------------------------------------- #
# Start job (requires explicit confirmation)
# --------------------------------------------------------------------------- #

def _to_image_state(image: ImageJob) -> ImageState:
    return ImageState(
        id=image.id,
        filename=image.filename,
        status=image.status,
        width=image.width,
        height=image.height,
        output_width=image.output_width,
        output_height=image.output_height,
        estimated_cost_usd=image.estimated_cost_usd,
        result_id=image.result_id,
        output_filename=image.output_filename if image.status is ImageStatus.DONE else None,
        error=image.error,
        duration_seconds=image.duration_seconds,
    )


def _to_job_response(job: Job) -> JobResponse:
    counts = job.counts()
    if job.finished:
        status = "complete"
    elif job.running:
        status = "processing"
    else:
        status = "queued"
    return JobResponse(
        job_id=job.id,
        scale_factor=job.scale_factor,
        creativity=job.creativity,
        output_suffix=job.output_suffix,
        output_format=job.output_format,
        concurrency=job.concurrency,
        status=status,
        total=job.total,
        completed=counts["completed"],
        succeeded=counts["succeeded"],
        failed=counts["failed"],
        timed_out=counts["timed_out"],
        images=[_to_image_state(i) for i in job.images.values()],
    )


@router.post("/jobs")
async def start_job(payload: StartJobRequest) -> JSONResponse:
    if payload.confirmed is not True:
        # The cost gate: no paid processing without explicit confirmation.
        raise HTTPException(
            status_code=400,
            detail="Processing must be explicitly confirmed before it can start.",
        )

    scan_record = manager.get_scan(payload.scan_id)
    if scan_record is None:
        raise HTTPException(
            status_code=404,
            detail="This estimate has expired. Please scan the images again.",
        )

    concurrency = clamp_concurrency(payload.concurrency)
    try:
        job = await manager.create_job_from_scan(payload.scan_id, concurrency)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="This estimate has expired. Please scan the images again.",
        )
    except RuntimeError:
        raise HTTPException(
            status_code=409, detail="This job has already been started."
        )

    # Kick off processing in the background; return immediately.
    asyncio.create_task(start_job_processing(job))
    return JSONResponse(content=_to_job_response(job).model_dump())


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JSONResponse(content=_to_job_response(job).model_dump())


# --------------------------------------------------------------------------- #
# Live progress (SSE)
# --------------------------------------------------------------------------- #

@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    queue = manager.subscribe(job_id)

    async def event_stream():
        # Send the current state immediately so late subscribers are in sync.
        yield _sse(manager.snapshot_event(job))
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Heartbeat comment keeps intermediaries from closing the pipe.
                    yield ": keep-alive\n\n"
                    if job.finished and job.total == 0:
                        break
                    continue
                yield _sse(event)
                if event.get("type") == "job_complete":
                    # Allow the client to receive the final event, then close.
                    break
        finally:
            manager.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# --------------------------------------------------------------------------- #
# Retry failed / timed out
# --------------------------------------------------------------------------- #

@router.post("/jobs/{job_id}/retry")
async def retry(job_id: str, payload: RetryRequest) -> JSONResponse:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.running:
        raise HTTPException(
            status_code=409, detail="This job is still processing. Please wait."
        )

    targets = manager.retryable_images(job, payload.image_ids)
    if not targets:
        raise HTTPException(
            status_code=400, detail="There are no failed or timed-out images to retry."
        )
    for image in targets:
        image.error = None
    asyncio.create_task(retry_images(job, targets))
    return JSONResponse(content=_to_job_response(job).model_dump())


# --------------------------------------------------------------------------- #
# Downloads
# --------------------------------------------------------------------------- #

@router.get("/results/{result_id}/download")
async def download_result(result_id: str) -> FileResponse:
    resolved = manager.resolve_result(result_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Result not found or expired.")
    _job, image = resolved
    if image.output_path is None or not image.output_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found or expired.")
    return FileResponse(
        path=image.output_path,
        media_type=content_type_for_ext(image.output_path.suffix),
        filename=image.output_filename,
    )


@router.get("/results/{result_id}/preview")
async def preview_result(result_id: str) -> StreamingResponse:
    """An optimised (downsized) preview of the upscaled output for the UI."""
    resolved = manager.resolve_result(result_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Result not found or expired.")
    _job, image = resolved
    if image.output_path is None or not image.output_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found or expired.")

    data = await asyncio.to_thread(_make_preview, image.output_path)
    return StreamingResponse(io.BytesIO(data), media_type="image/jpeg")


def _make_preview(path) -> bytes:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((_PREVIEW_MAX_EDGE, _PREVIEW_MAX_EDGE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_PREVIEW_QUALITY)
        return buf.getvalue()


@router.get("/jobs/{job_id}/download-all")
async def download_all(job_id: str) -> StreamingResponse:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    successful = [
        img
        for img in job.images.values()
        if img.status is ImageStatus.DONE
        and img.output_path is not None
        and img.output_path.exists()
    ]
    if not successful:
        raise HTTPException(
            status_code=400, detail="There are no completed images to download."
        )

    buffer = io.BytesIO()
    used_names: dict[str, int] = defaultdict(int)
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for image in successful:
            name = _unique_zip_name(image.output_filename, used_names)
            zf.write(image.output_path, arcname=name)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="qween-upscaled.zip"',
        },
    )


def _unique_zip_name(name: str, used: dict[str, int]) -> str:
    """Ensure ZIP entry names are unique and free of path components."""
    from pathlib import PurePosixPath

    safe = PurePosixPath(name).name or "image"
    if used[safe] == 0:
        used[safe] += 1
        return safe
    # Disambiguate duplicates: ring.jpg -> ring (2).jpg
    used[safe] += 1
    stem, dot, ext = safe.rpartition(".")
    if dot:
        return f"{stem} ({used[safe]}).{ext}"
    return f"{safe} ({used[safe]})"
