"""OpenAI provider — image edits for the Skin Fix tool.

Isolates the dependency on OpenAI's Images API. The only operation used is
``/v1/images/edits`` (inpainting-style edit): an input image, an optional PNG
mask (transparent = editable), a prompt and a target size. Returns the edited
image bytes.

The ``OPENAI_API_KEY`` lives only here on the backend and is never logged or
returned in a response.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache

import httpx

from ...core.logging import get_logger

log = get_logger("qween.provider.openai")

OPENAI_EDITS_URL = "https://api.openai.com/v1/images/edits"
_TIMEOUT = 300.0  # gpt-image edits can take a while


class OpenAIError(Exception):
    """Base class. ``message`` is safe to show to the user."""

    def __init__(self, message: str, *, technical: str | None = None):
        super().__init__(message)
        self.message = message
        self.technical = technical or message


class OpenAIAuthError(OpenAIError):
    """Authentication failed (bad or missing key)."""


class OpenAIBillingError(OpenAIError):
    """Billing / quota problem."""


@dataclass(frozen=True)
class EditResult:
    image_bytes: bytes


_BILLING_HINTS = ("billing", "quota", "insufficient", "exceeded", "payment", "credit")


class OpenAIProvider:
    def __init__(self, api_key: str, model: str):
        self._key = api_key or None
        self._model = model

    @property
    def configured(self) -> bool:
        return self._key is not None

    def _require(self) -> str:
        if not self._key:
            raise OpenAIAuthError(
                "OpenAI authentication failed.\n\n"
                "Please check the OPENAI_API_KEY configuration.",
                technical="OPENAI_API_KEY is not set on the backend.",
            )
        return self._key

    async def edit_image(
        self,
        *,
        image_bytes: bytes,
        image_filename: str,
        image_content_type: str,
        prompt: str,
        size: str,
        mask_bytes: bytes | None = None,
    ) -> EditResult:
        """Call ``/v1/images/edits`` and return the edited image bytes."""
        key = self._require()

        files = [
            ("image", (image_filename, image_bytes, image_content_type)),
        ]
        if mask_bytes is not None:
            files.append(("mask", ("mask.png", mask_bytes, "image/png")))

        data = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
            "n": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    OPENAI_EDITS_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    data=data,
                    files=files,
                )
        except httpx.HTTPError as exc:
            log.error("openai transport error: %s", exc)
            raise OpenAIError(
                "Couldn't reach OpenAI. Please try again.",
                technical=f"{type(exc).__name__}: {exc}",
            )

        if resp.status_code >= 400:
            raise self._classify(resp)

        try:
            payload = resp.json()
            b64 = payload["data"][0]["b64_json"]
            out = base64.b64decode(b64)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            log.error("openai unexpected result: %s", exc)
            raise OpenAIError(
                "OpenAI returned an unexpected result.",
                technical=f"parse: {exc}",
            )
        if not out:
            raise OpenAIError("OpenAI returned an empty image.")
        return EditResult(image_bytes=out)

    def _classify(self, resp: httpx.Response) -> OpenAIError:
        status = resp.status_code
        try:
            body = resp.json()
            message = (body.get("error") or {}).get("message") or resp.text
        except ValueError:
            message = resp.text
        technical = f"status={status}: {message[:300]}"
        log.error("openai edits failed: %s", technical)

        low = (message or "").lower()
        if status == 401:
            return OpenAIAuthError(
                "OpenAI authentication failed.\n\n"
                "Please check the OPENAI_API_KEY configuration.",
                technical=technical,
            )
        if status == 429 or any(h in low for h in _BILLING_HINTS):
            return OpenAIBillingError(
                "OpenAI billing or quota is not available.\n\n"
                "Please check the OpenAI account's billing/credits and try again.",
                technical=technical,
            )
        if status == 400 and "content" in low and "policy" in low:
            return OpenAIError(
                "This image was rejected by OpenAI's content policy.",
                technical=technical,
            )
        return OpenAIError("OpenAI returned an error.", technical=technical)


@lru_cache(maxsize=1)
def get_openai_provider() -> OpenAIProvider:
    from ...config import settings

    return OpenAIProvider(settings.openai_api_key, settings.openai_image_model)
