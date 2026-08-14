"""Batch worker: upload -> upscale -> download, per image, in isolation.

Every image is processed as an independent asyncio task guarded by:

* a shared :class:`asyncio.Semaphore` bounding concurrency, and
* an :func:`asyncio.wait_for` timeout so one stalled image can never block the
  rest of the batch.

A failure, timeout, or provider error affects only its own image; the batch
always runs to completion. State transitions and results are pushed to SSE
subscribers via the :class:`JobManager`.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from ..config import settings
from ..core.logging import get_logger
from ..providers.fal import FalError, get_provider
from ..storage import local as storage
from ..tools.upscaler.filenames import content_type_for_ext, safe_upload_name
from ..tools.upscaler.models import ImageStatus
from .manager import ImageJob, Job, manager

log = get_logger("qween.worker")

_DOWNLOAD_TIMEOUT = 60.0


def _set_status(job: Job, image: ImageJob, status: ImageStatus) -> None:
    image.status = status
    manager.emit_image_status(job, image)


async def _download_result(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def _process_one(job: Job, image: ImageJob) -> None:
    """Run the full pipeline for a single image. Never raises."""
    provider = get_provider()
    start = time.monotonic()
    log.info(
        "start image job_id=%s image_id=%s filename=%r dims=%dx%d scale=%d",
        job.id,
        image.id,
        image.filename,
        image.width,
        image.height,
        job.scale_factor,
    )
    try:
        # --- Stage 1: read input bytes ---
        try:
            data = image.input_path.read_bytes()
        except OSError as exc:
            raise FalError(
                "This image couldn't be read.", technical=f"read input: {exc}"
            )

        # --- Stage 1b: upload (sanitised filename, NOT the original) ---
        _set_status(job, image, ImageStatus.UPLOADING)
        content_type = content_type_for_ext(image.ext)
        safe_name = safe_upload_name(image.ext)
        uploaded_url = await provider.upload(data, content_type, safe_name)

        # --- Stage 2: upscale ---
        _set_status(job, image, ImageStatus.PROCESSING)
        result = await provider.upscale(
            uploaded_url, job.scale_factor, job.output_format
        )

        # --- Stage 3: download result ---
        _set_status(job, image, ImageStatus.DOWNLOADING)
        try:
            output_bytes = await _download_result(result.image_url)
        except httpx.HTTPError as exc:
            raise FalError(
                "Couldn't download the upscaled image from fal.ai.",
                technical=f"download result: {exc}",
            )

        # --- Persist output ---
        from ..tools.upscaler.filenames import output_extension

        out_ext = output_extension(job.output_format, image.ext)
        out_path = storage.output_path(job.id, image.id, out_ext)
        out_path.write_bytes(output_bytes)

        image.output_path = out_path
        image.result_id = manager.register_result(job.id, image.id)
        image.duration_seconds = round(time.monotonic() - start, 2)
        _set_status(job, image, ImageStatus.DONE)
        log.info(
            "done image_id=%s duration=%.2fs bytes=%d",
            image.id,
            image.duration_seconds,
            len(output_bytes),
        )
    except FalError as exc:
        image.error = exc.message
        image.duration_seconds = round(time.monotonic() - start, 2)
        _set_status(job, image, ImageStatus.FAILED)
        log.warning(
            "failed image_id=%s status=failed error=%s", image.id, exc.technical
        )
    except Exception as exc:  # noqa: BLE001 - defensive; isolate the image
        image.error = "This image couldn't be processed."
        image.duration_seconds = round(time.monotonic() - start, 2)
        _set_status(job, image, ImageStatus.FAILED)
        log.exception("unexpected failure image_id=%s: %s", image.id, exc)


async def _process_with_timeout(
    job: Job, image: ImageJob, semaphore: asyncio.Semaphore
) -> None:
    async with semaphore:
        try:
            await asyncio.wait_for(
                _process_one(job, image), timeout=settings.image_timeout_seconds
            )
        except asyncio.TimeoutError:
            image.error = (
                f"This image took longer than {settings.image_timeout_seconds} seconds."
            )
            image.status = ImageStatus.TIMEOUT
            manager.emit_image_status(job, image)
            log.warning(
                "timeout image_id=%s after %ss",
                image.id,
                settings.image_timeout_seconds,
            )


async def run_images(job: Job, images: list[ImageJob]) -> None:
    """Process the given images concurrently, then emit job completion."""
    if not images:
        job.running = False
        job.finished = True
        manager.emit_job_complete(job)
        return

    concurrency = max(1, min(job.concurrency, settings.max_concurrency, 8))
    semaphore = asyncio.Semaphore(concurrency)
    job.running = True

    # Reset the targeted images to queued and announce it.
    for image in images:
        _set_status(job, image, ImageStatus.QUEUED)

    tasks = [
        asyncio.create_task(_process_with_timeout(job, image, semaphore))
        for image in images
    ]
    # gather with return_exceptions so one crashing task can never abort others.
    await asyncio.gather(*tasks, return_exceptions=True)

    job.running = False
    job.finished = all(
        img.status in {ImageStatus.DONE, ImageStatus.FAILED, ImageStatus.TIMEOUT}
        for img in job.images.values()
    )
    manager.emit_job_complete(job)
    log.info("job complete job_id=%s counts=%s", job.id, job.counts())


async def start_job_processing(job: Job) -> None:
    await run_images(job, list(job.images.values()))


async def retry_images(job: Job, images: list[ImageJob]) -> None:
    await run_images(job, images)
