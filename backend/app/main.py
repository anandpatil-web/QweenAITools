"""QWEEN AI Tools — FastAPI application entrypoint.

Modular by design: each tool mounts its own router. Today there is one tool
(the Image Upscaler); future tools plug in the same way without the app or
other tools depending on the upscaler's implementation.
"""
from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .core.logging import get_logger
from .settings.router import router as settings_router
from .storage import local as storage
from .tools.upscaler.router import router as upscaler_router

log = get_logger("qween.app")

# Tool registry — future QWEEN AI tools register their router here.
TOOLS = [
    {
        "id": "upscaler",
        "name": "Image Upscaler",
        "description": "Enhance and upscale jewellery imagery while preserving detail.",
        "status": "available",
        "router": upscaler_router,
    },
]

_CLEANUP_INTERVAL_SECONDS = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.ensure_root()
    if not settings.fal_key_present:
        log.warning(
            "FAL_KEY is not set. Scan/estimate works, but processing will fail "
            "until a key is configured in the backend .env file."
        )
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task


async def _periodic_cleanup() -> None:
    while True:
        try:
            await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
            await asyncio.to_thread(storage.cleanup_expired)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("cleanup error: %s", exc)


app = FastAPI(title="QWEEN AI Tools", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak a stack trace to the client.
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "fal_configured": settings.fal_key_present,
        "supabase_configured": settings.supabase_configured,
    }


@app.get("/api/tools")
async def list_tools() -> dict:
    return {
        "tools": [
            {k: t[k] for k in ("id", "name", "description", "status")} for t in TOOLS
        ]
    }


app.include_router(settings_router)

for tool in TOOLS:
    app.include_router(tool["router"])
