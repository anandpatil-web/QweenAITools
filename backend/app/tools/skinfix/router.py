"""HTTP API for the Skin Fix tool."""
from __future__ import annotations

import asyncio
import io

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from ...config import settings
from ...core.logging import get_logger
from ...providers.openai import OpenAIError
from ..upscaler.validation import ImageValidationError
from .models import SkinFixMode, SkinFixStrength
from .service import make_preview, resolve_result, run_skin_fix

log = get_logger("qween.api.skinfix")

router = APIRouter(prefix="/api/skinfix", tags=["skinfix"])


def _parse_mode(raw: str) -> SkinFixMode:
    try:
        return SkinFixMode(raw)
    except ValueError:
        return SkinFixMode.MASKED


def _parse_strength(raw: str) -> SkinFixStrength:
    try:
        return SkinFixStrength(raw)
    except ValueError:
        return SkinFixStrength.STANDARD


@router.get("/config")
async def skinfix_config() -> dict:
    return {
        "openai_configured": settings.openai_configured,
        "model": settings.openai_image_model,
        "max_file_size_mb": settings.max_file_size_mb,
        "accepted_extensions": ["jpg", "jpeg", "png", "webp"],
    }


@router.post("")
async def skin_fix(
    image: UploadFile = File(...),
    mask: UploadFile | None = File(None),
    mode: str = Form("masked"),
    strength: str = Form("standard"),
) -> JSONResponse:
    image_data = await image.read()
    mask_data = await mask.read() if mask is not None else None

    try:
        result = await run_skin_fix(
            filename=image.filename or "image",
            content_type=image.content_type,
            image_data=image_data,
            mask_data=mask_data,
            mode=_parse_mode(mode),
            strength=_parse_strength(strength),
        )
    except ImageValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    except OpenAIError as exc:
        # User-safe message; the technical detail is logged inside the provider.
        raise HTTPException(status_code=502, detail=exc.message)

    return JSONResponse(content=result.model_dump())


@router.get("/results/{result_id}/download")
async def download_result(result_id: str) -> FileResponse:
    path = resolve_result(result_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Result not found or expired.")
    return FileResponse(path=path, media_type="image/png", filename=path.name)


@router.get("/results/{result_id}/preview")
async def preview_result(result_id: str) -> StreamingResponse:
    path = resolve_result(result_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Result not found or expired.")
    data = await asyncio.to_thread(make_preview, path)
    return StreamingResponse(io.BytesIO(data), media_type="image/jpeg")
