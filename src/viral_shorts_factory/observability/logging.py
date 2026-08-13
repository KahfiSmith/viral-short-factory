"""Structured JSON-lines logging.

Every log record is emitted as one JSON object per line: timestamp, level,
logger name, message, and any structured fields passed via ``extra``. Secret
values must never be passed to loggers — this module does not redact, callers
must not include them.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = getattr(record, "extra_fields", None)
        if isinstance(extras, dict):
            payload.update(extras)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _ExtraFilter(logging.Filter):
    """Move attributes of the record's ``extra`` dict into ``extra_fields``."""

    def __init__(self) -> None:
        super().__init__()
        self._seen: set[str] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        extras = getattr(record, "extra_fields", None)
        if extras is None:
            extras = {}
        for key in list(extras):
            if key in self._seen:  # pragma: no cover - defensive
                continue
            setattr(record, key, extras[key])
            self._seen.add(key)
        record.extra_fields = extras
        return True


def setup_logging(
    *,
    level: int = logging.INFO,
    log_path: Path | None = None,
    logger_name: str = "vsf",
) -> logging.Logger:
    """Configure the vsf logger with a JSON console handler and optional file.

    Returns the configured logger. Calling this more than once adds another
    file handler only if ``log_path`` differs from an existing one.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    formatter = JsonFormatter()

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    if log_path is not None:
        existing_files = {
            h.baseFilename for h in logger.handlers if isinstance(h, logging.FileHandler)
        }
        if str(log_path) not in existing_files:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
