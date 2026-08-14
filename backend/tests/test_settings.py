"""Settings service tests — validation, env fallback, unconfigured behaviour.

No network: the Supabase store is not configured in tests, so the service must
fall back to env defaults and reject writes with a clear error.
"""
from __future__ import annotations

import pytest

from app.providers.supabase import SupabaseError, get_settings_store
from app.settings import service


def test_store_not_configured_in_tests():
    # Without SUPABASE_URL/key the store reports unconfigured.
    assert get_settings_store().configured is False


@pytest.mark.asyncio
async def test_effective_settings_fall_back_to_env():
    eff = await service.get_effective_settings()
    assert eff["default_scale_factor"] == 2
    assert eff["default_output_format"] == "jpeg"
    assert eff["usd_to_inr"] > 0
    assert "default_concurrency" in eff


@pytest.mark.asyncio
async def test_update_rejected_when_unconfigured():
    with pytest.raises(SupabaseError):
        await service.update_settings({"default_scale_factor": 4})


def test_coerce_validates_and_clamps():
    out = service._coerce(
        {
            "default_scale_factor": 3,  # invalid -> dropped
            "default_concurrency": 99,  # clamped to <= max(8)
            "default_suffix": "_x2",
            "default_output_format": "jpg",  # normalised to jpeg
            "usd_to_inr": 85.5,
            "bogus": "ignored",
        }
    )
    assert "default_scale_factor" not in out
    assert out["default_concurrency"] <= 8
    assert out["default_suffix"] == "_x2"
    assert out["default_output_format"] == "jpeg"
    assert out["usd_to_inr"] == 85.5
    assert "bogus" not in out


def test_coerce_accepts_supported_scale():
    out = service._coerce({"default_scale_factor": 4})
    assert out["default_scale_factor"] == 4
