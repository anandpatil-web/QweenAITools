"""Pydantic schemas and shared enums for the upscaler tool."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ImageStatus(str, Enum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    DOWNLOADING = "downloading"
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


TERMINAL_STATUSES = {ImageStatus.DONE, ImageStatus.FAILED, ImageStatus.TIMEOUT}
RETRYABLE_STATUSES = {ImageStatus.FAILED, ImageStatus.TIMEOUT}


# ---------- Scan ----------

class ScannedImage(BaseModel):
    id: str
    filename: str
    width: int
    height: int
    input_megapixels: float
    output_width: int
    output_height: int
    output_megapixels: float
    estimated_cost_usd: float
    estimated_cost_inr: float


class ScanError(BaseModel):
    filename: str
    error: str


class ScanResponse(BaseModel):
    scan_id: str
    scale_factor: int
    output_suffix: str
    output_format: str
    images: list[ScannedImage]
    errors: list[ScanError] = Field(default_factory=list)
    total_images: int
    total_input_megapixels: float
    total_output_megapixels: float
    total_cost_usd: float
    total_cost_inr: float


# ---------- Jobs ----------

class StartJobRequest(BaseModel):
    scan_id: str
    confirmed: bool = False
    concurrency: int | None = None


class ImageState(BaseModel):
    id: str
    filename: str
    status: ImageStatus
    width: int
    height: int
    output_width: int
    output_height: int
    estimated_cost_usd: float
    result_id: str | None = None
    output_filename: str | None = None
    error: str | None = None
    duration_seconds: float | None = None


class JobResponse(BaseModel):
    job_id: str
    scale_factor: int
    output_suffix: str
    output_format: str
    concurrency: int
    status: str
    total: int
    completed: int
    succeeded: int
    failed: int
    timed_out: int
    images: list[ImageState]


class RetryRequest(BaseModel):
    image_ids: list[str] | None = None
