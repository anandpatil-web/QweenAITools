"""Prompt builder for the Skin Fix tool.

Encodes the QWEEN "natural_skin_fixer" brief: a high-end jewellery retoucher
that corrects excessive dryness/flaking while *preserving* real skin texture,
pores and imperfections — explicitly NOT beautifying. The backend additionally
composites the model output back over the original through the mask, so only
the brushed region can ever change (see service._composite_masked).
"""
from __future__ import annotations

from .models import SkinFixMode, SkinFixStrength

_BASE = (
    "You are a professional high-end jewellery retoucher specializing in realistic "
    "skin correction. Objective: correct excessive dryness, flaking, cracking and "
    "harsh exaggerated skin texture while keeping the skin completely natural and "
    "photorealistic, as if shot on a high-quality camera. "
    "Only reduce excessive dryness, visible flaking, exaggerated micro-texture, harsh "
    "surface cracking, and distracting deep micro-lines caused by dryness; subtly "
    "soften rough transitions and restore believable natural skin texture. "
    "Keep the skin naturally moisturized and healthy while RETAINING believable pores, "
    "fine lines, wrinkles, creases, tonal variation and natural imperfections. "
    "Do NOT change skin colour, undertone or tone; do NOT change hand, finger or body "
    "anatomy, proportions or nails; do NOT change jewellery or its position, clothing, "
    "background, lighting, shadows, composition, camera perspective or identity. "
    "Correction must be SUBTLE: low-to-medium texture reduction, very low smoothing, "
    "high retention of natural texture, zero beautification. "
    "Avoid at all costs: plastic, waxy, porcelain, airbrushed, over-smoothed or blurred "
    "skin, beauty-filter look, loss of pores or fine lines, fake or synthetic skin "
    "texture, repeating / tiled / cross-hatched / mesh texture, artificial gloss, wet "
    "skin, skin whitening or tone alteration, anatomy or finger deformation, and any "
    "jewellery, background or lighting alteration. "
    "Golden rule: do not make the skin beautiful — make the existing skin look naturally "
    "healthy while preserving its real texture and imperfections."
)

_MASKED_PREFIX = (
    "Correct the skin only inside the editable masked region and leave everything "
    "outside it completely untouched. "
)

_SUBTLE_SUFFIX = (
    " Apply the minimum correction necessary; when in doubt, leave the skin as it is."
)


def build_skinfix_prompt(mode: SkinFixMode, strength: SkinFixStrength) -> str:
    if mode is SkinFixMode.MASKED:
        prompt = _MASKED_PREFIX + _BASE
    else:
        prompt = _BASE
    if strength is SkinFixStrength.SUBTLE:
        prompt += _SUBTLE_SUFFIX
    return prompt
