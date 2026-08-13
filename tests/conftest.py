"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from viral_shorts_factory.config.models import AppConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = REPO_ROOT / "examples" / "config.example.yaml"


@pytest.fixture()
def example_config_path() -> Path:
    return EXAMPLE_CONFIG


@pytest.fixture()
def config(tmp_path: Path) -> AppConfig:
    """Load the shipped example config with paths redirected into tmp_path."""
    raw = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    raw["app"] = {
        "project_root": str(tmp_path / "projects"),
        "asset_library_root": str(tmp_path / "assets"),
        "database_path": str(tmp_path / "vsf.sqlite3"),
    }
    raw["video_use"] = {"repo_path": str(tmp_path / "video-use"), "require_strategy_approval": True}
    return AppConfig.model_validate(raw)


@pytest.fixture()
def video_fixture(tmp_path: Path) -> Path:
    """Generate a tiny portrait mp4 (1080x1920, 1s, tone audio) for tests."""
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg not available")
    path = tmp_path / "fixture.mp4"
    result = subprocess.run(  # noqa: S603 - fixed ffmpeg binary, array form, test fixture
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=1080x1920:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-y",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"ffmpeg fixture generation failed: {result.stderr}")
    return path
