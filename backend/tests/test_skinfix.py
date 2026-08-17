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
    assert "natural human skin" in full
    assert "masked region" in masked
    assert "masked region" not in full
    assert full != masked


def test_prompt_subtle_adds_suffix():
    subtle = build_skinfix_prompt(SkinFixMode.FULL, SkinFixStrength.SUBTLE)
    standard = build_skinfix_prompt(SkinFixMode.FULL, SkinFixStrength.STANDARD)
    assert "lightest touch" in subtle
    assert "lightest touch" not in standard


def test_composite_keeps_original_outside_mask():
    import io

    from PIL import Image

    from app.tools.skinfix.service import _composite_masked

    size = (64, 64)

    def png(color):
        b = io.BytesIO()
        Image.new("RGB", size, color).save(b, "PNG")
        return b.getvalue()

    orig = png((200, 0, 0))  # red original
    res = png((0, 0, 200))  # blue model output

    # Fully opaque mask = preserve everything -> output must equal original.
    opaque = io.BytesIO()
    Image.new("RGBA", size, (0, 0, 0, 255)).save(opaque, "PNG")
    out = _composite_masked(
        original_png=orig, result_png=res, mask_png=opaque.getvalue(), size=size
    )
    px = Image.open(io.BytesIO(out)).convert("RGB").getpixel((32, 32))
    assert px[0] > 150 and px[2] < 60  # still red

    # Fully transparent mask = editable everywhere -> output must equal result.
    transparent = io.BytesIO()
    Image.new("RGBA", size, (0, 0, 0, 0)).save(transparent, "PNG")
    out2 = _composite_masked(
        original_png=orig, result_png=res, mask_png=transparent.getvalue(), size=size
    )
    px2 = Image.open(io.BytesIO(out2)).convert("RGB").getpixel((32, 32))
    assert px2[2] > 150 and px2[0] < 60  # now blue
