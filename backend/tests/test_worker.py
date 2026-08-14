"""Batch worker tests: failure isolation, timeout, retry.

These use a FAKE provider injected only into the worker under test. This is a
unit-test double to exercise concurrency/failure logic — the running
application always uses the real fal.ai provider.
"""
from __future__ import annotations

import asyncio
import io

import pytest
from PIL import Image

from app.jobs import worker
from app.jobs.manager import JobManager, Scan, ScanImage
from app.providers.fal import FalError, UpscaleResult
from app.storage import local as storage
from app.tools.upscaler.models import ImageStatus


def _write_png(path, w=64, h=64):
    Image.new("RGB", (w, h), (1, 2, 3)).save(path, format="PNG")


class FakeProvider:
    """Succeeds for most images, fails/hangs for named ones."""

    def __init__(self, fail_ids=(), hang_ids=()):
        self.fail_ids = set(fail_ids)
        self.hang_ids = set(hang_ids)
        self.current = None

    async def upload(self, data, content_type, safe_filename):
        # Identify the image via the monkeypatched context set in _process_one.
        return "https://fake/uploaded"

    async def upscale(self, image_url, scale_factor, output_format):
        img_id = self.current
        if img_id in self.hang_ids:
            await asyncio.sleep(10)
        if img_id in self.fail_ids:
            raise FalError("fal.ai returned an error.")
        return UpscaleResult(image_url="https://fake/result", output_format=output_format)


async def _fake_download(url: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (128, 128), (9, 9, 9)).save(buf, format="JPEG")
    return buf.getvalue()


def _build_job(mgr: JobManager, n: int):
    scan_id = mgr.new_scan_id()
    storage.ensure_root()
    images = []
    for i in range(n):
        img_id = mgr.new_image_id()
        p = storage.input_path(scan_id, img_id, ".png")
        _write_png(p)
        images.append(
            ScanImage(
                id=img_id, filename=f"img{i}.png", ext=".png", width=64, height=64,
                output_width=128, output_height=128, input_megapixels=0.004,
                output_megapixels=0.016, estimated_cost_usd=0.0003, input_path=p,
            )
        )
    mgr.register_scan(Scan(id=scan_id, scale_factor=2, output_suffix="",
                           output_format="jpeg", images=images))
    return scan_id, [im.id for im in images]


@pytest.mark.asyncio
async def test_failure_isolation(monkeypatch):
    mgr = JobManager()
    monkeypatch.setattr(worker, "manager", mgr)
    scan_id, ids = _build_job(mgr, 5)

    fake = FakeProvider(fail_ids={ids[1]})

    # Make _process_one aware of which image the provider is handling.
    original = worker._process_one

    async def tracking_process_one(job, image):
        fake.current = image.id
        await original(job, image)

    monkeypatch.setattr(worker, "get_provider", lambda: fake)
    monkeypatch.setattr(worker, "_download_result", _fake_download)
    monkeypatch.setattr(worker, "_process_one", tracking_process_one)

    job = await mgr.create_job_from_scan(scan_id, concurrency=4)
    await worker.start_job_processing(job)

    counts = job.counts()
    assert counts["succeeded"] == 4
    assert counts["failed"] == 1
    assert job.images[ids[1]].status is ImageStatus.FAILED
    assert job.finished is True


@pytest.mark.asyncio
async def test_timeout_does_not_block_batch(monkeypatch):
    mgr = JobManager()
    monkeypatch.setattr(worker, "manager", mgr)
    from types import SimpleNamespace
    monkeypatch.setattr(
        worker, "settings", SimpleNamespace(image_timeout_seconds=1, max_concurrency=4)
    )

    scan_id, ids = _build_job(mgr, 3)
    fake = FakeProvider(hang_ids={ids[0]})

    original = worker._process_one

    async def tracking_process_one(job, image):
        fake.current = image.id
        await original(job, image)

    monkeypatch.setattr(worker, "get_provider", lambda: fake)
    monkeypatch.setattr(worker, "_download_result", _fake_download)
    monkeypatch.setattr(worker, "_process_one", tracking_process_one)

    job = await mgr.create_job_from_scan(scan_id, concurrency=4)
    await worker.start_job_processing(job)

    assert job.images[ids[0]].status is ImageStatus.TIMEOUT
    assert job.counts()["succeeded"] == 2


@pytest.mark.asyncio
async def test_retry_only_failed(monkeypatch):
    mgr = JobManager()
    monkeypatch.setattr(worker, "manager", mgr)
    scan_id, ids = _build_job(mgr, 3)

    fake = FakeProvider(fail_ids={ids[0]})
    original = worker._process_one

    async def tracking_process_one(job, image):
        fake.current = image.id
        await original(job, image)

    monkeypatch.setattr(worker, "get_provider", lambda: fake)
    monkeypatch.setattr(worker, "_download_result", _fake_download)
    monkeypatch.setattr(worker, "_process_one", tracking_process_one)

    job = await mgr.create_job_from_scan(scan_id, concurrency=4)
    await worker.start_job_processing(job)
    assert job.counts()["failed"] == 1

    # Now let the previously-failing image succeed on retry.
    fake.fail_ids = set()
    targets = mgr.retryable_images(job, None)
    assert len(targets) == 1
    await worker.retry_images(job, targets)
    assert job.counts()["succeeded"] == 3
    assert job.counts()["failed"] == 0
