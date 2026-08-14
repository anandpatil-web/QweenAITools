"""Authoritative cost calculation for the Crystal Upscaler.

Pricing model (from the fal.ai Crystal Upscaler):

    cost_usd = output_megapixels * 0.016

where ``output_megapixels`` is derived from the *output* dimensions, i.e. the
input dimensions multiplied by the scale factor.

The backend is the single source of truth for cost. The frontend may compute a
preview but must never be trusted for billing decisions.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...config import CRYSTAL_USD_PER_MEGAPIXEL, settings


@dataclass(frozen=True)
class CostBreakdown:
    input_width: int
    input_height: int
    scale_factor: float
    output_width: int
    output_height: int
    input_megapixels: float
    output_megapixels: float
    estimated_cost_usd: float


def _megapixels(width: int, height: int) -> float:
    return (width * height) / 1_000_000.0


def calculate_cost(width: int, height: int, scale_factor: float) -> CostBreakdown:
    """Compute the authoritative per-image cost breakdown."""
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive.")
    if scale_factor <= 0:
        raise ValueError("Scale factor must be positive.")

    output_width = round(width * scale_factor)
    output_height = round(height * scale_factor)
    input_mp = _megapixels(width, height)
    output_mp = _megapixels(output_width, output_height)
    cost = output_mp * CRYSTAL_USD_PER_MEGAPIXEL

    return CostBreakdown(
        input_width=width,
        input_height=height,
        scale_factor=scale_factor,
        output_width=output_width,
        output_height=output_height,
        input_megapixels=round(input_mp, 4),
        output_megapixels=round(output_mp, 4),
        estimated_cost_usd=round(cost, 4),
    )


def usd_to_inr(usd: float) -> float:
    """Convert USD to an approximate INR figure for display only."""
    return round(usd * settings.usd_to_inr, 2)
