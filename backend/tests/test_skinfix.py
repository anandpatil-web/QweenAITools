"""Skin Fix tests — size computation and prompt building (no OpenAI)."""
from __future__ import annotations

from app.tools.skinfix.models import SkinFixMode, SkinFixStrength
from app.tools.skinfix.prompts import build_skinfix_prompt
from app.tools.skinfix.service import compute_output_size


def test_output_size_multiple_of_16():
    w, h = compute_output_size(1000, 1000)
    assert w % 16 == 0 and h % 16 == 0


def test_output_size_caps_at_2048():
    w, h = compute_output_size(6000, 4000)
    assert max(w, h) <= 2048


def test_output_size_clamps_extreme_aspect():
    w, h = compute_output_size(5000, 500)  # 10:1 -> clamp to <= 3:1
    assert max(w / h, h / w) <= 3.01


def test_prompt_full_vs_masked():
    full = build_skinfix_prompt(SkinFixMode.FULL, SkinFixStrength.STANDARD)
    masked = build_skinfix_prompt(SkinFixMode.MASKED, SkinFixStrength.STANDARD)
    assert "this photo" in full
    assert "masked region" in masked
    assert full != masked


def test_prompt_subtle_adds_suffix():
    subtle = build_skinfix_prompt(SkinFixMode.FULL, SkinFixStrength.SUBTLE)
    standard = build_skinfix_prompt(SkinFixMode.FULL, SkinFixStrength.STANDARD)
    assert "minimum change" in subtle
    assert "minimum change" not in standard
