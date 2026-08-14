"""Local temporary storage for job inputs and upscaled outputs.

Layout::

    /tmp/qween-ai-tools/
        jobs/
            {job_id}/
                inputs/
                outputs/

Everything is treated as ephemeral. Results older than ``RESULT_TTL_MINUTES``
are removed by :func:`cleanup_expired`. All paths are derived from
server-generated ids only — never from a user-supplied filename — so there is
no path-traversal surface.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import time
from pathlib import Path

from ..config import settings
from ..core.logging import get_logger

log = get_logger("qween.storage")

_ROOT = Path(tempfile.gettempdir()) / "qween-ai-tools"
_JOBS_ROOT = _ROOT / "jobs"

# Server-generated ids only ever contain these characters. We still validate
# defensively before using an id to build a path.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]+$")


def _safe_id(value: str) -> str:
    if not value or not _SAFE_ID.match(value):
        raise ValueError(f"Unsafe storage id: {value!r}")
    return value


def ensure_root() -> None:
    _JOBS_ROOT.mkdir(parents=True, exist_ok=True)


def job_dir(job_id: str) -> Path:
    path = _JOBS_ROOT / _safe_id(job_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def inputs_dir(job_id: str) -> Path:
    path = job_dir(job_id) / "inputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def outputs_dir(job_id: str) -> Path:
    path = job_dir(job_id) / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def input_path(job_id: str, image_id: str, ext: str) -> Path:
    """Path for a stored original image, keyed only by server-generated ids."""
    ext = _normalise_ext(ext)
    return inputs_dir(job_id) / f"{_safe_id(image_id)}{ext}"


def output_path(job_id: str, image_id: str, ext: str) -> Path:
    ext = _normalise_ext(ext)
    return outputs_dir(job_id) / f"{_safe_id(image_id)}{ext}"


def _normalise_ext(ext: str) -> str:
    ext = ext.lower().strip()
    if not ext.startswith("."):
        ext = "." + ext
    # Only allow a small, known set of characters in an extension.
    if not re.match(r"^\.[a-z0-9]{1,5}$", ext):
        raise ValueError(f"Unsafe extension: {ext!r}")
    return ext


def delete_job(job_id: str) -> None:
    try:
        path = _JOBS_ROOT / _safe_id(job_id)
    except ValueError:
        return
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def cleanup_expired() -> int:
    """Remove job directories whose mtime is older than the TTL.

    Returns the number of job directories removed.
    """
    ttl_seconds = max(1, settings.result_ttl_minutes) * 60
    now = time.time()
    removed = 0
    if not _JOBS_ROOT.exists():
        return 0
    for entry in _JOBS_ROOT.iterdir():
        if not entry.is_dir():
            continue
        try:
            age = now - entry.stat().st_mtime
        except OSError:
            continue
        if age > ttl_seconds:
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    if removed:
        log.info("Cleaned up %d expired job(s)", removed)
    return removed
