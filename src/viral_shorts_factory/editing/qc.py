"""Quality Control (QC) validation engine for final rendered videos (docs/03, docs/05 M11)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from viral_shorts_factory.assets.probe import ProbeError, probe_video
from viral_shorts_factory.config.models import AppConfig, ProfileConfig


class QCCheckResult(BaseModel):
    """Result of an individual QC check."""

    name: str
    passed: bool
    details: str


class QCReport(BaseModel):
    """Full QC report persisted to project workspace (docs/05 M11)."""

    passed: bool
    checks: list[QCCheckResult] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2) + "\n"


class QCError(Exception):
    """Raised when QC execution or validation fails fatally."""


def qc_report_from_json(text: str) -> QCReport:
    try:
        return QCReport.model_validate(json.loads(text))
    except Exception as exc:
        raise QCError(f"invalid QC report JSON: {exc}") from exc


def run_qc(
    final_video_path: Path,
    config: AppConfig,
    profile_config: ProfileConfig,
) -> QCReport:
    """Run mandatory QC checks on the final rendered video.

    Validates file existence, non-zero size, ffprobe readability, video stream,
    vertical aspect ratio, target resolution, and profile duration bounds.
    """
    checks: list[QCCheckResult] = []

    # Check 1: File existence and size > 0
    if not final_video_path.is_file():
        checks.append(
            QCCheckResult(
                name="file_exists",
                passed=False,
                details=f"file not found at {final_video_path}",
            )
        )
        return QCReport(passed=False, checks=checks)

    size = final_video_path.stat().st_size
    if size == 0:
        checks.append(
            QCCheckResult(
                name="file_size",
                passed=False,
                details="file size is 0 bytes",
            )
        )
        return QCReport(passed=False, checks=checks)
    else:
        checks.append(
            QCCheckResult(
                name="file_size",
                passed=True,
                details=f"file size is {size} bytes",
            )
        )

    # Check 2: Readable by ffprobe and valid video stream
    try:
        probe = probe_video(final_video_path)
        checks.append(
            QCCheckResult(
                name="ffprobe_readable",
                passed=True,
                details=f"codec={probe.video_codec}, fps={probe.fps:.2f}",
            )
        )
    except ProbeError as exc:
        checks.append(
            QCCheckResult(
                name="ffprobe_readable",
                passed=False,
                details=f"ffprobe failed: {exc}",
            )
        )
        return QCReport(passed=False, checks=checks)

    # Check 3: Aspect ratio (vertical: height > width)
    is_vertical = probe.height > probe.width
    checks.append(
        QCCheckResult(
            name="aspect_ratio_vertical",
            passed=is_vertical,
            details=f"dimensions {probe.width}x{probe.height} (vertical={is_vertical})",
        )
    )

    # Check 4: Resolution target check
    target_w = config.defaults.width
    target_h = config.defaults.height
    res_ok = probe.width == target_w and probe.height == target_h
    checks.append(
        QCCheckResult(
            name="resolution_target",
            passed=res_ok,
            details=f"expected {target_w}x{target_h}, got {probe.width}x{probe.height}",
        )
    )

    # Check 5: Duration bounds check
    min_d = float(profile_config.min_duration_seconds)
    max_d = float(profile_config.max_duration_seconds)
    dur_ok = min_d <= probe.duration_seconds <= max_d
    checks.append(
        QCCheckResult(
            name="duration_within_bounds",
            passed=dur_ok,
            details=(
                f"duration {probe.duration_seconds:.2f}s "
                f"expected between {min_d:.1f}s and {max_d:.1f}s"
            ),
        )
    )

    all_passed = all(c.passed for c in checks)
    return QCReport(passed=all_passed, checks=checks)
