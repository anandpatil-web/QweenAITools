"""fal.ai provider — upload + Crystal Upscaler.

This module isolates every direct dependency on the ``fal-client`` SDK so the
rest of the application depends on a small, stable interface. Two stages are
exposed:

1. :meth:`FalProvider.upload` — upload raw image bytes to fal storage using a
   *sanitised* filename (never the user's original name, which can contain
   characters that break the upload with "Illegal header value").
2. :meth:`FalProvider.upscale` — call ``clarityai/crystal-upscaler`` and return
   the resulting image URL.

Errors are translated into a small typed hierarchy with user-safe messages.
The technical cause is logged on the backend; the ``FAL_KEY`` is never logged.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import fal_client
import httpx

from ...core.logging import get_logger

log = get_logger("qween.provider.fal")

CRYSTAL_UPSCALER_APP = "clarityai/crystal-upscaler"

# The Crystal Upscaler only accepts these literal output_format values. Our
# internal canonical name is "jpeg" (matching MIME/Pillow), so we translate at
# the fal boundary: fal rejects "jpeg" with a 422 and wants "jpg".
_FAL_OUTPUT_FORMAT = {"jpeg": "jpg", "jpg": "jpg", "png": "png"}


def _fal_output_format(value: str) -> str:
    return _FAL_OUTPUT_FORMAT.get((value or "").lower(), "jpg")


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

class FalError(Exception):
    """Base class. ``message`` is safe to show to the user."""

    def __init__(self, message: str, *, technical: str | None = None):
        super().__init__(message)
        self.message = message
        self.technical = technical or message


class FalBillingError(FalError):
    """fal.ai billing / credits are not configured."""


class FalAuthError(FalError):
    """fal.ai authentication failed (bad or missing key)."""


class FalUploadError(FalError):
    """The image could not be uploaded to fal storage."""


class FalResultError(FalError):
    """fal.ai returned an unexpected / empty result."""


_BILLING_HINTS = (
    "billing",
    "credit",
    "exhausted",
    "balance",
    "payment",
    "subscription",
    "quota",
    "insufficient",
    "top up",
    "top-up",
)


def _status_code_of(exc: BaseException) -> int | None:
    """Best-effort extraction of an HTTP status code from an SDK exception."""
    seen = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        response = getattr(cur, "response", None)
        if response is not None and getattr(response, "status_code", None):
            return int(response.status_code)
        cur = cur.__cause__ or cur.__context__
    return None


def _looks_like_billing(text: str) -> bool:
    low = text.lower()
    return any(hint in low for hint in _BILLING_HINTS)


def _classify(exc: Exception, *, stage: str) -> FalError:
    """Translate an SDK/HTTP exception into a typed, user-safe error."""
    technical = f"{type(exc).__name__}: {exc}"
    status = _status_code_of(exc)
    message_text = str(exc)

    if status in (401, 402, 403):
        # A 401 during upload is, per fal.ai behaviour, most commonly a
        # billing/credits problem rather than a bad key. We prefer the message
        # text when it clearly points one way, then fall back to the stage.
        if status == 402 or _looks_like_billing(message_text):
            return FalBillingError(
                "fal.ai billing or credits are not configured.\n\n"
                "Please add billing/credits to the fal.ai account and try again.",
                technical=technical,
            )
        if stage == "upload" and status == 401:
            return FalBillingError(
                "fal.ai billing or credits are not configured.\n\n"
                "Please add billing/credits to the fal.ai account and try again.",
                technical=technical,
            )
        return FalAuthError(
            "fal.ai authentication failed.\n\n"
            "Please check the FAL_KEY configuration.",
            technical=technical,
        )

    if stage == "upload":
        return FalUploadError(
            "Couldn't upload this image to fal.ai.", technical=technical
        )
    return FalError("fal.ai returned an error.", technical=technical)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UpscaleResult:
    image_url: str
    output_format: str


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class FalProvider:
    """Thin async wrapper around the fal-client SDK."""

    def __init__(self, key: str | None):
        # An empty key is allowed at construction time; the missing-key case is
        # surfaced as a clear auth error when a call is actually attempted.
        self._key = key or None
        self._client = fal_client.AsyncClient(key=self._key) if self._key else None

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _require_client(self) -> fal_client.AsyncClient:
        if self._client is None:
            raise FalAuthError(
                "fal.ai authentication failed.\n\n"
                "Please check the FAL_KEY configuration.",
                technical="FAL_KEY is not set on the backend.",
            )
        return self._client

    async def upload(self, data: bytes, content_type: str, safe_filename: str) -> str:
        """Upload image bytes and return the fal storage URL.

        ``safe_filename`` MUST be a sanitised, server-generated name such as
        ``input.jpg`` — never the user's original filename.
        """
        client = self._require_client()
        try:
            return await client.upload(data, content_type, safe_filename)
        except (fal_client.client.FalClientError, httpx.HTTPStatusError) as exc:
            err = _classify(exc, stage="upload")
            log.error("fal upload failed: %s", err.technical)
            raise err
        except httpx.HTTPError as exc:
            log.error("fal upload transport error: %s", exc)
            raise FalUploadError(
                "Couldn't upload this image to fal.ai.",
                technical=f"{type(exc).__name__}: {exc}",
            )

    async def upscale(
        self, image_url: str, scale_factor: int, output_format: str
    ) -> UpscaleResult:
        """Run the Crystal Upscaler and return the resulting image URL."""
        client = self._require_client()
        arguments: dict[str, Any] = {
            "image_url": image_url,
            "scale_factor": scale_factor,
            "output_format": _fal_output_format(output_format),
        }
        try:
            result = await client.subscribe(CRYSTAL_UPSCALER_APP, arguments=arguments)
        except (fal_client.client.FalClientError, httpx.HTTPStatusError) as exc:
            err = _classify(exc, stage="process")
            log.error("crystal-upscaler failed: %s", err.technical)
            raise err
        except httpx.HTTPError as exc:
            log.error("crystal-upscaler transport error: %s", exc)
            raise FalError(
                "fal.ai returned an error.",
                technical=f"{type(exc).__name__}: {exc}",
            )

        url = _extract_image_url(result)
        if not url:
            log.error("crystal-upscaler unexpected result shape: %r", _shape(result))
            raise FalResultError("fal.ai returned an unexpected result.")
        return UpscaleResult(image_url=url, output_format=output_format)


def _extract_image_url(result: Any) -> str | None:
    """Extract the first image URL from the Crystal Upscaler response.

    Expected shape::

        {"images": [{"url": "https://..."}]}

    We tolerate a couple of common variants defensively.
    """
    if not isinstance(result, dict):
        return None
    images = result.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict) and isinstance(first.get("url"), str):
            return first["url"]
        if isinstance(first, str):
            return first
    # Some fal apps return a single "image" object.
    image = result.get("image")
    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return image["url"]
    return None


def _shape(result: Any) -> Any:
    """Return a compact description of a result for safe logging."""
    if isinstance(result, dict):
        return {k: type(v).__name__ for k, v in result.items()}
    return type(result).__name__


@lru_cache(maxsize=1)
def get_provider() -> FalProvider:
    from ...config import settings

    return FalProvider(settings.fal_key)
