"""Schemas and enums for the Skin Fix tool."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class SkinFixMode(str, Enum):
    MASKED = "masked"
    FULL = "full"


class SkinFixStrength(str, Enum):
    SUBTLE = "subtle"
    STANDARD = "standard"


class SkinFixResult(BaseModel):
    result_id: str
    output_filename: str
    width: int
    height: int
    size: str
    mode: SkinFixMode
    strength: SkinFixStrength
    # Full result inline (data:image/png;base64,...) so the browser can display
    # and download it without a second request — resilient to free-tier
    # instance spin-down/restart wiping the stored file.
    image_data_url: str
