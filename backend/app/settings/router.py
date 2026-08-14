"""System settings & prompts API (optional Supabase-backed)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..providers.supabase import SupabaseError, get_settings_store
from .service import EDITABLE_KEYS, get_effective_settings, update_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    default_scale_factor: float | None = None
    default_concurrency: int | None = None
    default_suffix: str | None = None
    default_output_format: str | None = None
    usd_to_inr: float | None = None


class PromptUpsert(BaseModel):
    tool_id: str = "upscaler"
    name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(default="", max_length=20000)


@router.get("")
async def read_settings() -> dict:
    effective = await get_effective_settings()
    return {
        "configured": settings.supabase_configured,
        "editable_keys": list(EDITABLE_KEYS),
        "settings": effective,
    }


@router.put("")
async def write_settings(payload: SettingsUpdate) -> dict:
    try:
        effective = await update_settings(payload.model_dump(exclude_none=True))
    except SupabaseError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return {"configured": True, "settings": effective}


@router.get("/prompts")
async def list_prompts(tool_id: str = "upscaler") -> dict:
    store = get_settings_store()
    if not store.configured:
        return {"configured": False, "prompts": []}
    try:
        prompts = await store.list_prompts(tool_id)
    except SupabaseError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return {"configured": True, "prompts": prompts}


@router.put("/prompts")
async def upsert_prompt(payload: PromptUpsert) -> dict:
    store = get_settings_store()
    if not store.configured:
        raise HTTPException(
            status_code=400,
            detail="Supabase is not configured, so prompts can't be saved.",
        )
    try:
        row = await store.upsert_prompt(payload.tool_id, payload.name, payload.prompt)
    except SupabaseError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return {"prompt": row}


@router.delete("/prompts")
async def delete_prompt(name: str, tool_id: str = "upscaler") -> dict:
    store = get_settings_store()
    if not store.configured:
        raise HTTPException(
            status_code=400,
            detail="Supabase is not configured, so prompts can't be deleted.",
        )
    try:
        await store.delete_prompt(tool_id, name)
    except SupabaseError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return {"deleted": True}
