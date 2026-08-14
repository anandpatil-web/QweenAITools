"""Structured, secret-safe logging helpers.

The logger deliberately never accepts the ``FAL_KEY``. A ``redact`` filter
scrubs anything that looks like a fal credential from log records as a
defence-in-depth measure so a stray interpolation can never leak the key.
"""
from __future__ import annotations

import logging
import re
import sys

_FAL_KEY_PATTERN = re.compile(r"[A-Za-z0-9\-]{8,}:[A-Za-z0-9\-]{8,}")


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        if _FAL_KEY_PATTERN.search(message):
            record.msg = _FAL_KEY_PATTERN.sub("<redacted>", message)
            record.args = ()
        return True


_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    )
    handler.addFilter(_RedactFilter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
