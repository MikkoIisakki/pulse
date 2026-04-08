"""Structured logging configuration for the application."""

import logging
import sys

from app.common.config import settings


def configure_logging() -> None:
    """Configure root logger. Call once at application startup."""
    logging.basicConfig(
        stream=sys.stdout,
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
