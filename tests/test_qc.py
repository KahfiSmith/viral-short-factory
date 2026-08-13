"""Tests for Quality Control (QC) validation (Milestone 11)."""

from __future__ import annotations

from pathlib import Path

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.editing.qc import run_qc


def test_qc_pass(config: AppConfig, video_fixture: Path):
    profile = config.profiles["football_comedy"]
    # Override profile bounds for tiny test fixture
    profile_override = profile.model_copy(
        update={"min_duration_seconds": 0, "max_duration_seconds": 10}
    )

    report = run_qc(video_fixture, config, profile_override)
    assert report.passed is True
    assert len(report.checks) == 5


def test_qc_missing_file(config: AppConfig, tmp_path: Path):
    missing_path = tmp_path / "non_existent.mp4"
    profile = config.profiles["football_comedy"]

    report = run_qc(missing_path, config, profile)
    assert report.passed is False
    assert report.checks[0].name == "file_exists"
    assert report.checks[0].passed is False
