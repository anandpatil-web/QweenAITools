"""System settings service.

Merges optional Supabase-stored settings on top of the environment defaults.
The environment is always the baseline; Supabase (when configured) provides
editable overrides for a small, validated set of keys. If Supabase is not
configured — or a read fails — we silently fall back to env defaults so the
tool always works.
"""
from __future__ import annotations

from typing import Any

from ..config import (
    ALLOWED_OUTPUT_FORMATS,
    SUPPORTED_SCALE_FACTORS,
    settings,
)
from ..core.logging import get_logger
from ..providers.supabase import SupabaseError, get_settings_store

log = get_logger("qween.settings")

UPSCALER_TOOL_ID = "upscaler"

# Only these keys may be overridden from the settings store, each validated.
EDITABLE_KEYS = (
    "default_scale_factor",
    "default_concurrency",
    "default_suffix",
    "default_output_format",
    "usd_to_inr",
)


def _env_defaults() -> dict[str, Any]:
    return {
        "default_scale_factor": 2,
        "default_concurrency": min(4, settings.max_concurrency),
        "default_suffix": "",
        "default_output_format": "jpeg",
        "usd_to_inr": settings.usd_to_inr,
    }


def _coerce(values: dict[str, Any]) -> dict[str, Any]:
    """Validate/clamp a partial settings dict; drop anything invalid."""
    out: dict[str, Any] = {}
    for key in EDITABLE_KEYS:
        if key not in values or values[key] is None:
            continue
        raw = values[key]
        try:
            if key == "default_scale_factor":
                v = int(raw)
                if v in SUPPORTED_SCALE_FACTORS:
                    out[key] = v
            elif key == "default_concurrency":
                v = int(raw)
                out[key] = max(1, min(v, settings.max_concurrency, 8))
            elif key == "default_suffix":
                out[key] = str(raw)[:40]
            elif key == "default_output_format":
                v = str(raw).lower()
                if v == "jpg":
                    v = "jpeg"
                if v in ALLOWED_OUTPUT_FORMATS:
                    out[key] = v
            elif key == "usd_to_inr":
                v = float(raw)
                if 0 < v < 100000:
                    out[key] = round(v, 4)
        except (TypeError, ValueError):
            continue
    return out


async def get_effective_settings() -> dict[str, Any]:
    """Env defaults overlaid with valid stored overrides (if any)."""
    effective = _env_defaults()
    store = get_settings_store()
    if not store.configured:
        return effective
    try:
        stored = await store.get_settings(UPSCALER_TOOL_ID)
    except SupabaseError as exc:
        log.warning("settings read failed, using env defaults: %s", exc.technical)
        return effective
    effective.update(_coerce(stored))
    return effective


async def update_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist a partial settings update; return the effective set."""
    store = get_settings_store()
    if not store.configured:
        raise SupabaseError(
            "Supabase is not configured, so settings can't be saved. "
            "Add SUPABASE_URL and the service key to backend/.env.",
            technical="store not configured",
        )
    clean = _coerce(values)
    if not clean:
        raise SupabaseError(
            "No valid settings were provided.", technical="empty after validation"
        )
    # Merge onto whatever is already stored so a partial update is non-destructive.
    current = {}
    try:
        current = await store.get_settings(UPSCALER_TOOL_ID)
    except SupabaseError:
        current = {}
    merged = {**_coerce(current), **clean}
    await store.upsert_settings(UPSCALER_TOOL_ID, merged)
    return {**_env_defaults(), **merged}
