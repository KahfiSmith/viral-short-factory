"""ffprobe metadata extraction tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from viral_shorts_factory.assets.probe import ProbeError, probe_video


def test_probe_video_metadata(video_fixture: Path) -> None:
    result = probe_video(video_fixture)
    assert result.width == 1080
    assert result.height == 1920
    assert result.duration_seconds > 0.5
    assert result.video_codec == "h264"
    assert result.has_audio is True
    assert result.fps > 0


def test_probe_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="not a file"):
        probe_video(tmp_path / "nope.mp4")


def test_probe_non_video_raises(tmp_path: Path) -> None:
    path = tmp_path / "not_video.mp4"
    path.write_bytes(b"this is not a video")
    with pytest.raises(ProbeError):
        probe_video(path)
