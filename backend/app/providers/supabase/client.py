"""Supabase-backed store for system settings and prompts.

This is an *optional* provider. When ``SUPABASE_URL`` and a service key are set,
the backend persists per-tool settings and prompt templates in two small
tables via the Supabase REST (PostgREST) API. When it is not configured, the
store reports ``configured == False`` and callers fall back to env defaults —
so the app remains fully functional locally with no database, exactly as V1
intended.

We talk to PostgREST directly with httpx (already a dependency) rather than
pulling in the full supabase-py SDK, to keep the footprint minimal.

Tables (create these in the Supabase SQL editor):

    create table if not exists app_settings (
        tool_id    text primary key,
        settings   jsonb not null default '{}'::jsonb,
        updated_at timestamptz not null default now()
    );

    create table if not exists app_prompts (
        id         uuid primary key default gen_random_uuid(),
        tool_id    text not null,
        name       text not null,
        prompt     text not null default '',
        updated_at timestamptz not null default now(),
        unique (tool_id, name)
    );

The service key bypasses row-level security, so these tables are only ever
reachable from the backend — never exposed to the browser.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx

from ...config import settings
from ...core.logging import get_logger

log = get_logger("qween.provider.supabase")

_TIMEOUT = 10.0


class SupabaseError(Exception):
    """User-safe error from the settings store."""

    def __init__(self, message: str, *, technical: str | None = None):
        super().__init__(message)
        self.message = message
        self.technical = technical or message


class SupabaseSettingsStore:
    """Minimal async client for the settings/prompts tables."""

    def __init__(self, url: str, service_key: str):
        self._base = f"{url}/rest/v1" if url else ""
        self._key = service_key
        self._configured = bool(url and service_key)

    @property
    def configured(self) -> bool:
        return self._configured

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _require(self) -> None:
        if not self._configured:
            raise SupabaseError(
                "Supabase is not configured on the backend.",
                technical="SUPABASE_URL / service key missing.",
            )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self._require()
        url = f"{self._base}{path}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            log.error("supabase transport error: %s", exc)
            raise SupabaseError(
                "Couldn't reach the settings store.",
                technical=f"{type(exc).__name__}: {exc}",
            )
        if resp.status_code >= 400:
            log.error(
                "supabase %s %s -> %s: %s",
                method,
                path,
                resp.status_code,
                resp.text[:300],
            )
            if resp.status_code in (401, 403):
                raise SupabaseError(
                    "Supabase rejected the request. Check the service key.",
                    technical=f"status={resp.status_code}",
                )
            if resp.status_code == 404 or "does not exist" in resp.text:
                raise SupabaseError(
                    "The settings tables are missing. Run the setup SQL in Supabase.",
                    technical=resp.text[:300],
                )
            raise SupabaseError(
                "The settings store returned an error.",
                technical=f"status={resp.status_code}",
            )
        return resp

    # -------------------------------------------------------------- settings

    async def get_settings(self, tool_id: str) -> dict[str, Any]:
        resp = await self._request(
            "GET",
            f"/app_settings?tool_id=eq.{tool_id}&select=settings",
            headers=self._headers(),
        )
        rows = resp.json()
        if isinstance(rows, list) and rows:
            value = rows[0].get("settings")
            return value if isinstance(value, dict) else {}
        return {}

    async def upsert_settings(self, tool_id: str, values: dict[str, Any]) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            "/app_settings?on_conflict=tool_id",
            headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
            json=[{"tool_id": tool_id, "settings": values}],
        )
        rows = resp.json()
        if isinstance(rows, list) and rows:
            return rows[0].get("settings", values)
        return values

    # --------------------------------------------------------------- prompts

    async def list_prompts(self, tool_id: str) -> list[dict[str, Any]]:
        resp = await self._request(
            "GET",
            f"/app_prompts?tool_id=eq.{tool_id}&select=name,prompt,updated_at&order=name.asc",
            headers=self._headers(),
        )
        rows = resp.json()
        return rows if isinstance(rows, list) else []

    async def upsert_prompt(self, tool_id: str, name: str, prompt: str) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            "/app_prompts?on_conflict=tool_id,name",
            headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
            json=[{"tool_id": tool_id, "name": name, "prompt": prompt}],
        )
        rows = resp.json()
        if isinstance(rows, list) and rows:
            return rows[0]
        return {"tool_id": tool_id, "name": name, "prompt": prompt}

    async def delete_prompt(self, tool_id: str, name: str) -> None:
        await self._request(
            "DELETE",
            f"/app_prompts?tool_id=eq.{tool_id}&name=eq.{name}",
            headers=self._headers(prefer="return=minimal"),
        )


@lru_cache(maxsize=1)
def get_settings_store() -> SupabaseSettingsStore:
    return SupabaseSettingsStore(settings.supabase_url, settings.supabase_service_key)
