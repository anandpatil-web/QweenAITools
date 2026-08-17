"""Prompt builder for the Skin Fix tool.

Action-first phrasing: flake removal is the imperative; preservation rules
follow. Generalised beyond faces (works for hands, arms, décolletage, face)
and it explicitly forbids synthetic / repeating / tiled texture — gpt-image
otherwise tends to invent a cross-hatch "skin pattern" instead of sampling the
real surrounding skin.
"""
from __future__ import annotations

from .models import SkinFixMode, SkinFixStrength

_NO_SYNTH = (
    "Do NOT invent, add, or overlay any synthetic, repeating, tiled, "
    "cross-hatched, mesh, netted, scaly or patterned texture. Sample and match "
    "the real texture, pore size and grain of the adjacent healthy skin. No "
    "beauty smoothing, airbrushing, frequency-separation softness, or plastic / "
    "waxy / blurred look."
)

_FULL = (
    "Remove all skin flaking, dryness, peeling, cracking and rough scaly patches "
    "in this photo. Replace them with smooth, healthy, naturally hydrated skin "
    "that seamlessly matches the tone, colour, lighting and real texture of the "
    "surrounding healthy skin. The flakes must be completely gone — do not leave "
    "them partially visible. " + _NO_SYNTH + " Keep the subject's identity, "
    "anatomy, pose, camera angle, lighting direction, shadow placement, contrast, "
    "exposure, colour grading, jewellery and metal reflections, clothing, and "
    "background exactly as provided. Preserve genuine pores, fine lines, wrinkles "
    "and natural skin character. Photorealistic result."
)

_MASKED = (
    "Inside the editable masked region only, remove all skin flaking, dryness, "
    "peeling and rough scaly patches, and replace them with smooth healthy skin "
    "that blends invisibly into the surrounding healthy skin's tone, lighting, "
    "shadows, specular highlights and real texture. The flakes must be completely "
    "gone. " + _NO_SYNTH + " Preserve genuine pores, fine lines and natural "
    "character. Leave everything outside the masked region untouched. Photorealistic."
)

_SUBTLE_SUFFIX = (
    " Make the minimum change necessary while still fully removing the flaking; "
    "when in doubt, keep the existing healthy skin."
)


def build_skinfix_prompt(mode: SkinFixMode, strength: SkinFixStrength) -> str:
    prompt = _FULL if mode is SkinFixMode.FULL else _MASKED
    if strength is SkinFixStrength.SUBTLE:
        prompt += _SUBTLE_SUFFIX
    return prompt
