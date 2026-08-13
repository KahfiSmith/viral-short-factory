"""Local asset library service tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from viral_shorts_factory.assets.library import (
    AssetLibrary,
    AssetLibraryError,
    local_first_search,
)
from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetSearchRequest, RightsStatus
from viral_shorts_factory.persistence.repositories import DatabaseConnection


@pytest.fixture()
def library(config: AppConfig) -> AssetLibrary:
    conn = DatabaseConnection(config)
    return AssetLibrary(conn, config)


def test_register_hashes_probes_and_stores(video_fixture: Path, library: AssetLibrary) -> None:
    entry = library.register(
        video_fixture,
        category="football",
        tags=["Goalkeeper", " Soccer "],
        rights_status=RightsStatus.PROVIDER_LICENSED,
    )
    assert entry.asset_id.startswith("asset_")
    assert entry.width == 1080
    assert entry.height == 1920
    assert entry.orientation == "portrait"
    assert entry.duration_seconds > 0.5
    assert entry.tags == ["goalkeeper", "soccer"]  # normalized lowercase
    assert entry.rights_status == RightsStatus.PROVIDER_LICENSED.value
    assert len(entry.sha256) == 64


def test_register_duplicate_prevention(video_fixture: Path, library: AssetLibrary) -> None:
    first = library.register(video_fixture, tags=["a"])
    second = library.register(video_fixture, tags=["a"])
    assert first.asset_id == second.asset_id
    assert library.find_by_sha256(first.sha256) is not None
    # Only one row in the library.
    assert len(library.search()) == 1


def test_register_defaults_to_unverified(video_fixture: Path, library: AssetLibrary) -> None:
    entry = library.register(video_fixture)
    assert entry.rights_status == RightsStatus.UNVERIFIED.value


def test_register_missing_file_raises(library: AssetLibrary, tmp_path: Path) -> None:
    with pytest.raises(AssetLibraryError, match="not a file"):
        library.register(tmp_path / "nope.mp4")


def test_search_by_tag_and_category(video_fixture: Path, library: AssetLibrary) -> None:
    library.register(video_fixture, category="football", tags=["goalkeeper", "soccer"])
    assert len(library.search(tags=["goalkeeper"])) == 1
    assert len(library.search(category="football")) == 1
    assert len(library.search(tags=["nonexistent"])) == 0
    assert len(library.search(category="other")) == 0


def test_local_first_search_maps_to_candidates(video_fixture: Path, library: AssetLibrary) -> None:
    library.register(
        video_fixture, tags=["goalkeeper"], rights_status=RightsStatus.PROVIDER_LICENSED
    )
    request = AssetSearchRequest(scene_id="s1", query="goalkeeper", minimum_height=1080)
    candidates = local_first_search(library, request)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.candidate_id.startswith("local:")
    assert candidate.provider == "local"
    assert candidate.width == 1080
    assert candidate.height == 1920
    assert candidate.rights_status == RightsStatus.PROVIDER_LICENSED


def test_local_first_search_respects_max_results(library: AssetLibrary, tmp_path: Path) -> None:
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg not available")
    for i in range(3):
        p = tmp_path / f"v{i}.mp4"
        subprocess.run(  # noqa: S603 - fixed ffmpeg binary, array form, test fixture
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x240:rate=10",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={400 + i}:sample_rate=8000",
                "-t",
                "0.3",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-y",
                str(p),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        library.register(p, tags=["clip"])

    request = AssetSearchRequest(scene_id="s1", query="clip", max_results=2)
    assert len(local_first_search(library, request)) == 2


def test_mark_used_and_reuse_across_projects(
    video_fixture: Path, library: AssetLibrary, config: AppConfig
) -> None:
    """Acceptance: an asset registered once is reusable in a second project
    with no network provider involved."""
    from datetime import UTC, datetime

    from viral_shorts_factory.domain.project import Project
    from viral_shorts_factory.persistence.repositories import ProjectRepository

    conn = DatabaseConnection(config)
    project_repo = ProjectRepository(conn)
    now = datetime(2026, 8, 12, tzinfo=UTC)
    project_repo.create(
        Project(
            project_id="project-a",
            profile="football_comedy",
            topic="a",
            target_duration_seconds=28,
            created_at=now,
            updated_at=now,
        )
    )
    project_repo.create(
        Project(
            project_id="project-b",
            profile="football_comedy",
            topic="b",
            target_duration_seconds=28,
            created_at=now,
            updated_at=now,
        )
    )

    entry = library.register(
        video_fixture, tags=["goal"], rights_status=RightsStatus.PROVIDER_LICENSED
    )
    library.mark_used(entry.asset_id, "project-a", scene_id="scene_001")
    library.mark_used(entry.asset_id, "project-b", scene_id="scene_002")

    loaded = library.get(entry.asset_id)
    assert loaded.use_count == 2
    assert loaded.last_used_at is not None

    # Second project finds it locally by tag.
    request = AssetSearchRequest(scene_id="s2", query="goal", minimum_height=1080)
    candidates = local_first_search(library, request)
    assert [c.provider_asset_id for c in candidates] == [entry.asset_id]
    assert candidates[0].provider == "local"
