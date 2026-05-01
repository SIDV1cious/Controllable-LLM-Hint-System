"""Small error-handling helpers used across UI and service modules."""

from __future__ import annotations

import logging


def log_exception(context: str, exc: Exception) -> None:
    """Log exceptions with a stable context label for easier debugging."""
    logging.exception("%s: %s", context, exc)


def friendly_error(action: str) -> str:
    return f"{action}失败，请稍后重试或联系管理员。"
