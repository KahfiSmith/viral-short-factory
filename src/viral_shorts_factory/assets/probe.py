"""ffprobe metadata extraction for video files."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProbeError(Exception):
    """Raised when a video cannot be probed."""


@dataclass(frozen=True)
class ProbeResult:
    """Normalized ffprobe metadata."""

    duration_seconds: float
    width: int
    height: int
    fps: float
    video_codec: str
    has_audio: bool


def probe_video(path: Path) -> ProbeResult:
    """Probe a video file with ffprobe and return normalized metadata."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise ProbeError("ffprobe not found on PATH")
    if not path.is_file():
        raise ProbeError(f"not a file: {path}")

    try:
        result = subprocess.run(  # noqa: S603 - fixed binary, array form, path is a bound arg
            [ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(f"ffprobe failed for {path}: {exc}") from exc

    if result.returncode != 0:
        raise ProbeError(
            f"ffprobe could not read {path}: {result.stderr.strip() or 'unknown error'}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"invalid ffprobe output for {path}") from exc

    return _parse_streams(data, path)


def _parse_streams(data: dict[str, Any], path: Path) -> ProbeResult:
    """Extract video/audio stream info from ffprobe JSON."""
    video: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video is None:
            video = stream
        elif codec_type == "audio" and audio is None:
            audio = stream

    if video is None:
        raise ProbeError(f"no video stream in {path}")

    try:
        duration = float(video.get("duration", 0.0) or 0.0)
        width = int(video.get("width", 0))
        height = int(video.get("height", 0))
        fps = _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
        codec = video.get("codec_name", "")
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"unparseable stream metadata in {path}") from exc

    return ProbeResult(
        duration_seconds=duration,
        width=width,
        height=height,
        fps=fps,
        video_codec=codec,
        has_audio=audio is not None,
    )


def _parse_fps(rate: str) -> float:
    """Parse a ffmpeg frame-rate string like '30/1' or '30000/1001'."""
    parts = rate.split("/")
    if len(parts) != 2:
        return float(rate or 0)
    num, den = float(parts[0]), float(parts[1])
    return num / den if den else 0.0
