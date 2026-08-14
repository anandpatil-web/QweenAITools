"""In-memory job & scan state plus a per-job SSE event bus.

V1 keeps everything in process memory (no database). A single ``JobManager``
instance owns:

* **scans** — the validated, cost-estimated inputs produced by ``/api/scan``.
  Input bytes are written to disk at scan time so images are never re-uploaded
  from the browser when a job starts.
* **jobs** — running/finished batches. Each job holds per-image state and a set
  of asyncio subscriber queues used to fan out Server-Sent Events.
* **results** — a map from an opaque ``result_id`` to the (job, image) that
  produced it, used by the download endpoints.

Job/scan/image/result ids are generated server-side (uuid4 hex) and are the
only values ever used to build filesystem paths.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..core.logging import get_logger
from ..tools.upscaler.models import (
    RETRYABLE_STATUSES,
    TERMINAL_STATUSES,
    ImageStatus,
)

log = get_logger("qween.jobs")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class ScanImage:
    id: str
    filename: str  # original, user-facing name (metadata only)
    ext: str  # canonical extension of the stored input
    width: int
    height: int
    output_width: int
    output_height: int
    input_megapixels: float
    output_megapixels: float
    estimated_cost_usd: float
    input_path: Path


@dataclass
class Scan:
    id: str
    scale_factor: int
    output_suffix: str
    output_format: str
    images: list[ScanImage]
    started: bool = False


@dataclass
class ImageJob:
    id: str
    filename: str
    ext: str
    width: int
    height: int
    output_width: int
    output_height: int
    estimated_cost_usd: float
    input_path: Path
    output_filename: str
    status: ImageStatus = ImageStatus.QUEUED
    result_id: str | None = None
    output_path: Path | None = None
    output_format: str = "jpeg"
    error: str | None = None
    duration_seconds: float | None = None


@dataclass
class Job:
    id: str
    scale_factor: int
    output_suffix: str
    output_format: str
    concurrency: int
    images: dict[str, ImageJob]
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    running: bool = False
    finished: bool = False

    @property
    def total(self) -> int:
        return len(self.images)

    def counts(self) -> dict[str, int]:
        succeeded = sum(1 for i in self.images.values() if i.status is ImageStatus.DONE)
        failed = sum(1 for i in self.images.values() if i.status is ImageStatus.FAILED)
        timed_out = sum(
            1 for i in self.images.values() if i.status is ImageStatus.TIMEOUT
        )
        completed = sum(
            1 for i in self.images.values() if i.status in TERMINAL_STATUSES
        )
        return {
            "completed": completed,
            "succeeded": succeeded,
            "failed": failed,
            "timed_out": timed_out,
        }


class JobManager:
    def __init__(self) -> None:
        self._scans: dict[str, Scan] = {}
        self._jobs: dict[str, Job] = {}
        self._results: dict[str, tuple[str, str]] = {}  # result_id -> (job_id, image_id)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ scans

    def new_scan_id(self) -> str:
        return _new_id("scan")

    def new_image_id(self) -> str:
        return _new_id("img")

    def register_scan(self, scan: Scan) -> None:
        self._scans[scan.id] = scan

    def get_scan(self, scan_id: str) -> Scan | None:
        return self._scans.get(scan_id)

    # ------------------------------------------------------------------- jobs

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def create_job_from_scan(self, scan_id: str, concurrency: int) -> Job:
        """Promote a scan into a running job. Guards against double-start."""
        from ..tools.upscaler.filenames import build_output_filename

        async with self._lock:
            scan = self._scans.get(scan_id)
            if scan is None:
                raise KeyError("scan_not_found")
            if scan.started or scan_id in self._jobs:
                raise RuntimeError("job_already_started")
            scan.started = True

            images: dict[str, ImageJob] = {}
            for si in scan.images:
                images[si.id] = ImageJob(
                    id=si.id,
                    filename=si.filename,
                    ext=si.ext,
                    width=si.width,
                    height=si.height,
                    output_width=si.output_width,
                    output_height=si.output_height,
                    estimated_cost_usd=si.estimated_cost_usd,
                    input_path=si.input_path,
                    output_filename=build_output_filename(
                        si.filename, scan.output_suffix, scan.output_format
                    ),
                    output_format=scan.output_format,
                    status=ImageStatus.QUEUED,
                )
            job = Job(
                id=scan_id,
                scale_factor=scan.scale_factor,
                output_suffix=scan.output_suffix,
                output_format=scan.output_format,
                concurrency=concurrency,
                images=images,
            )
            self._jobs[job.id] = job
            return job

    # -------------------------------------------------------------- results

    def register_result(self, job_id: str, image_id: str) -> str:
        result_id = _new_id("res")
        self._results[result_id] = (job_id, image_id)
        return result_id

    def resolve_result(self, result_id: str) -> tuple[Job, ImageJob] | None:
        entry = self._results.get(result_id)
        if not entry:
            return None
        job_id, image_id = entry
        job = self._jobs.get(job_id)
        if not job:
            return None
        image = job.images.get(image_id)
        if not image:
            return None
        return job, image

    # ------------------------------------------------------------------- SSE

    def subscribe(self, job_id: str) -> asyncio.Queue:
        job = self._jobs[job_id]
        queue: asyncio.Queue = asyncio.Queue()
        job.subscribers.add(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        job = self._jobs.get(job_id)
        if job and queue in job.subscribers:
            job.subscribers.discard(queue)

    def publish(self, job_id: str, event: dict) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        for queue in list(job.subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - unbounded queues
                pass

    def snapshot_event(self, job: Job) -> dict:
        counts = job.counts()
        return {
            "type": "snapshot",
            "job_id": job.id,
            "total": job.total,
            **counts,
            "images": [
                {
                    "image_id": img.id,
                    "status": img.status.value,
                    "result_id": img.result_id,
                    "output_filename": img.output_filename,
                    "error": img.error,
                }
                for img in job.images.values()
            ],
        }

    def emit_image_status(self, job: Job, image: ImageJob) -> None:
        event = {
            "type": "image_status",
            "image_id": image.id,
            "status": image.status.value,
        }
        if image.result_id:
            event["result_id"] = image.result_id
            event["output_filename"] = image.output_filename
        if image.error:
            event["error"] = image.error
        self.publish(job.id, event)
        # Always follow an image update with an aggregate progress event.
        counts = job.counts()
        self.publish(
            job.id,
            {
                "type": "job_progress",
                "completed": counts["completed"],
                "total": job.total,
            },
        )

    def emit_job_complete(self, job: Job) -> None:
        counts = job.counts()
        self.publish(
            job.id,
            {"type": "job_complete", "job_id": job.id, "total": job.total, **counts},
        )

    def retryable_images(self, job: Job, image_ids: list[str] | None) -> list[ImageJob]:
        if image_ids:
            wanted = set(image_ids)
            candidates = [
                img
                for img in job.images.values()
                if img.id in wanted and img.status in RETRYABLE_STATUSES
            ]
        else:
            candidates = [
                img for img in job.images.values() if img.status in RETRYABLE_STATUSES
            ]
        return candidates


# A single process-wide manager instance.
manager = JobManager()
