"""Prompt builder for the Skin Fix tool (ported from the QWEEN studio).

Action-first phrasing: the repair is the imperative; preservation rules follow
so the model treats flake removal as the primary task rather than tying it with
"preserve every micro-detail".
"""
from __future__ import annotations

from .models import SkinFixMode, SkinFixStrength

_FULL = (
    "Repair every patch of skin flakiness, dryness, peeling, and surface scaling in "
    "this photo. Replace those rough scaly patches with smooth, healthy, well-hydrated "
    "skin that still shows natural pores and realistic skin texture at the same grain "
    "level as the surrounding healthy areas. The flakes must be gone — do not leave them "
    "partially visible. Do not apply beauty smoothing, airbrushing, frequency-separation "
    "softness, or any plastic / waxy / blurred look. Keep facial structure, identity, "
    "expression, age, ethnicity, hair, jewelry and metal reflections, clothing, pose, "
    "camera angle, lighting direction, shadow placement, contrast, exposure, color "
    "grading, and background exactly as provided. Preserve fine lines, wrinkles, beard "
    "stubble, and facial character. Photorealistic result."
)

_MASKED = (
    "Inside the editable masked region, repair every patch of skin flakiness, dryness, "
    "peeling, and surface scaling. Replace those rough scaly patches with smooth, "
    "healthy, well-hydrated skin showing natural pores and realistic skin texture that "
    "matches the surrounding healthy skin's tone, lighting, shadows, and specular "
    "highlights so the repair blends seamlessly. The flakes must be gone — do not leave "
    "them partially visible. No beauty smoothing, airbrushing, or plastic / waxy / "
    "blurred look. Preserve fine lines, wrinkles, beard stubble, and facial character. "
    "Photorealistic."
)

_SUBTLE_SUFFIX = (
    " Make the minimum change necessary; when in doubt, leave the skin as it is."
)


def build_skinfix_prompt(mode: SkinFixMode, strength: SkinFixStrength) -> str:
    prompt = _FULL if mode is SkinFixMode.FULL else _MASKED
    if strength is SkinFixStrength.SUBTLE:
        prompt += _SUBTLE_SUFFIX
    return prompt
