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
