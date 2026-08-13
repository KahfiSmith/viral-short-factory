"""Structured logging tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from viral_shorts_factory.observability.logging import setup_logging


def test_json_lines_written_to_file(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"
    logger = setup_logging(level=logging.INFO, log_path=log_path, logger_name="vsf.test")

    logger.info(
        "stage_completed",
        extra={"extra_fields": {"run_id": "run_1", "stage": "INIT", "event": "stage_completed"}},
    )

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["message"] == "stage_completed"
    assert record["event"] == "stage_completed"
    assert record["stage"] == "INIT"
    assert record["run_id"] == "run_1"
    assert "timestamp" in record
    assert "level" in record


def test_no_secrets_in_output(tmp_path: Path) -> None:
    log_path = tmp_path / "no_secrets.jsonl"
    logger = setup_logging(level=logging.INFO, log_path=log_path, logger_name="vsf.secret")

    logger.info(
        "provider_search",
        extra={"extra_fields": {"provider": "pexels", "api_key_env": "PEXELS_API_KEY"}},
    )

    content = log_path.read_text(encoding="utf-8")
    assert "sk-" not in content
    assert "PEXELS_API_KEY" in content  # the env-var NAME is fine, the value is not


def test_logger_reuse_does_not_duplicate_handlers(tmp_path: Path) -> None:
    log_path = tmp_path / "once.jsonl"
    logger = setup_logging(level=logging.INFO, log_path=log_path, logger_name="vsf.reuse")
    logger.info("one", extra={"extra_fields": {"event": "one"}})
    logger.info("two", extra={"extra_fields": {"event": "two"}})

    # Re-invoking with the same path must not add a second file handler.
    setup_logging(level=logging.INFO, log_path=log_path, logger_name="vsf.reuse")
    logger.info("three", extra={"extra_fields": {"event": "three"}})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
