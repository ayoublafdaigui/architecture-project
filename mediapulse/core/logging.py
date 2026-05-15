"""Logging configuration helpers for MediaPulse."""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Configure process-wide structured-enough console logging."""

    try:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    except Exception:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).exception("Failed to configure logging")
