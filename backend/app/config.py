"""Application configuration loaded from environment variables.

All settings are read once at import time from the process environment
(populated from a local ``.env`` via python-dotenv). The ``FAL_KEY`` lives
only here on the backend and is never returned in an API response.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load the backend/.env first, then a repo-root .env as a fallback so either
# location works for local development.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_REPO_ROOT / ".env")


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# Crystal Upscaler price: USD per output megapixel.
CRYSTAL_USD_PER_MEGAPIXEL = 0.016

# Scale factors supported by the Crystal Upscaler.
SUPPORTED_SCALE_FACTORS = (2, 4)

# Allowed concurrency choices shown in the UI.
ALLOWED_CONCURRENCY = (1, 2, 4, 8)

# Accepted image formats.
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_OUTPUT_FORMATS = ("jpeg", "png")


@dataclass(frozen=True)
class Settings:
    fal_key: str = field(default_factory=lambda: os.getenv("FAL_KEY", "").strip())
    usd_to_inr: float = field(default_factory=lambda: _get_float("USD_TO_INR", 90.0))
    max_concurrency: int = field(default_factory=lambda: _get_int("MAX_CONCURRENCY", 4))
    image_timeout_seconds: int = field(
        default_factory=lambda: _get_int("IMAGE_TIMEOUT_SECONDS", 180)
    )
    max_file_size_mb: int = field(default_factory=lambda: _get_int("MAX_FILE_SIZE_MB", 50))
    result_ttl_minutes: int = field(default_factory=lambda: _get_int("RESULT_TTL_MINUTES", 60))
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _get_int("PORT", 8000))
    # Optional Supabase-backed system settings/prompts store. Backend only.
    supabase_url: str = field(
        default_factory=lambda: os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    )
    supabase_service_key: str = field(
        default_factory=lambda: (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_KEY")
            or ""
        ).strip()
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        )
    )

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def fal_key_present(self) -> bool:
        return bool(self.fal_key)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


settings = Settings()
