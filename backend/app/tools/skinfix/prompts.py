"""Prompt builder for the Skin Fix tool — QWEEN natural_skin_fixer v2.0.

v2 strategy: the *source* skin texture may itself be unnatural/AI-generated
(flaky, cracked, over-detailed), so it is NOT preserved — the skin surface is
reconstructed into believable natural human skin. Tone, undertone, anatomy,
jewellery, lighting, composition and background ARE preserved. The backend
additionally composites the output back over the original through the mask, so
in masked mode only the brushed region is reconstructed.
"""
from __future__ import annotations

from .models import SkinFixMode, SkinFixStrength

_BASE = (
    "Edit the provided image to replace unnatural, AI-generated skin texture with "
    "realistic, natural human skin. The source skin texture may be excessively flaky, "
    "dry, cracked, rough or overly detailed, so do NOT treat the existing skin texture "
    "as something that must be preserved — reconstruct the skin surface where necessary. "
    "Preserve the person's skin tone, undertone, anatomy, proportions, hands, fingers, "
    "nails, jewellery, lighting, shadows, highlights, composition, background and camera "
    "perspective exactly. "
    "Reconstruct believable natural human skin: subtle realistic pores and fine texture "
    "with natural tonal variation, no dryness, no flaking, no cracking, low roughness, "
    "very low smoothing, a natural matte finish with realistic light response. Keep "
    "subtle believable human imperfections, but remove obvious AI artifacts and "
    "unnatural texture. "
    "Skin must look like real human skin photographed with a high-quality camera. Do not "
    "copy the flaky or cracked texture from the source and do not preserve AI-generated "
    "artifacts. Do not make the skin perfectly smooth or remove all pores. No porcelain, "
    "plastic, waxy, glossy, airbrushed, over-smoothed or blurred skin; no beauty-filter "
    "retouching; no artificial polish or gloss; no wet skin. Do not whiten, brighten, "
    "recolour or change the natural skin tone. Maintain realistic texture variation "
    "across the hand and keep joints, knuckles, folds and creases anatomically "
    "believable. "
    "Do not modify jewellery in any way (size, shape, position, material, stones, "
    "reflections, details), hand or finger anatomy, finger length/width/joints/"
    "proportions, nails, clothing, background, composition, camera angle, or lighting "
    "direction and intensity. "
    "Golden rule: preserve the person and the photograph, not the bad skin texture. "
    "Reconstruct the skin surface when the source texture is unnatural, while keeping the "
    "result subtle, realistic and completely human — a high-quality photograph, not an "
    "AI-generated skin replacement."
)

_MASKED_PREFIX = (
    "Reconstruct the skin only inside the editable masked region and leave everything "
    "outside it completely untouched. "
)

_SUBTLE_SUFFIX = (
    " Keep the reconstruction restrained — correct the unnatural texture with the "
    "lightest touch that still removes the flaking and cracking."
)


def build_skinfix_prompt(mode: SkinFixMode, strength: SkinFixStrength) -> str:
    prompt = (_MASKED_PREFIX + _BASE) if mode is SkinFixMode.MASKED else _BASE
    if strength is SkinFixStrength.SUBTLE:
        prompt += _SUBTLE_SUFFIX
    return prompt
