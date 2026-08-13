"""Resume-point and asset-library repository tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import Project
from viral_shorts_factory.domain.states import Stage, next_stage_after
from viral_shorts_factory.persistence.repositories import (
    AssetLibraryEntry,
    AssetLibraryRepository,
    DatabaseConnection,
    ProjectRepository,
)

FIXED_NOW = datetime(2026, 8, 12, tzinfo=UTC)


def _make_project(project_id: str) -> Project:
    return Project(
        project_id=project_id,
        profile="football_comedy",
        topic="test",
        target_duration_seconds=28,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


@pytest.fixture()
def conn(tmp_path: Path, config: AppConfig) -> DatabaseConnection:
    config.app.database_path = tmp_path / "resume.sqlite3"
    return DatabaseConnection(config)


def test_interrupted_run_resumes_at_next_stage(conn: DatabaseConnection) -> None:
    """An interrupted run leaves status persisted; resume computes the next stage."""
    repo = ProjectRepository(conn)
    repo.create(_make_project("20260812-run-00000000"))
    chain = [
        Stage.BRIEF_READY,
        Stage.CONCEPT_READY,
        Stage.SCRIPT_READY,
        Stage.STORYBOARD_READY,
        Stage.ASSET_QUERIES_READY,
        Stage.ASSETS_DISCOVERED,
        Stage.ASSETS_SELECTED,
    ]
    for stage in chain:
        repo.update_status("20260812-run-00000000", stage, "run_1")

    loaded = repo.get("20260812-run-00000000")
    assert loaded is not None
    assert loaded.status.value == "ASSETS_SELECTED"
    assert next_stage_after(loaded.status).value == "EDIT_BRIEF_READY"


def test_next_stage_after_chain() -> None:
    from viral_shorts_factory.domain.states import Stage

    assert next_stage_after(Stage.INIT) == Stage.BRIEF_READY
    assert next_stage_after(Stage.BRIEF_READY) == Stage.CONCEPT_READY
    assert next_stage_after(Stage.AWAITING_EDIT_STRATEGY_APPROVAL) == Stage.EDITING
    assert next_stage_after(Stage.QC) == Stage.COMPLETE
    assert next_stage_after(Stage.COMPLETE) is None
    assert next_stage_after(Stage.FAILED_RETRYABLE) is None  # caller picks target


def test_asset_register_and_find_by_sha256(conn: DatabaseConnection) -> None:
    repo = AssetLibraryRepository(conn)
    entry = AssetLibraryEntry(
        asset_id="asset_1",
        local_path="/sources/a.mp4",
        sha256="abc123",
        category="football",
        tags=["goalkeeper", "soccer"],
        rights_status="PROVIDER_LICENSED",
    )
    repo.register(entry)
    found = repo.find_by_sha256("abc123")
    assert found is not None
    assert found.asset_id == "asset_1"
    assert found.tags == ["goalkeeper", "soccer"]


def test_asset_search_by_category_and_tags(conn: DatabaseConnection) -> None:
    repo = AssetLibraryRepository(conn)
    repo.register(
        AssetLibraryEntry(
            asset_id="a1",
            local_path="/1.mp4",
            sha256="s1",
            category="football",
            tags=["goalkeeper"],
            rights_status="PROVIDER_LICENSED",
        )
    )
    repo.register(
        AssetLibraryEntry(
            asset_id="a2",
            local_path="/2.mp4",
            sha256="s2",
            category="city",
            tags=["traffic"],
            rights_status="PROVIDER_LICENSED",
        )
    )
    assert [e.asset_id for e in repo.search(category="football")] == ["a1"]
    assert [e.asset_id for e in repo.search(tags=["goalkeeper"])] == ["a1"]
    assert len(repo.search()) == 2


def test_asset_defaults_to_unverified(conn: DatabaseConnection) -> None:
    repo = AssetLibraryRepository(conn)
    repo.register(AssetLibraryEntry(asset_id="u1", local_path="/u.mp4", sha256="u"))
    assert repo.get("u1").rights_status == "UNVERIFIED"


def test_asset_mark_used(conn: DatabaseConnection) -> None:
    project_repo = ProjectRepository(conn)
    project_repo.create(_make_project("20260812-use-00000000"))
    lib = AssetLibraryRepository(conn)
    lib.register(
        AssetLibraryEntry(
            asset_id="a1",
            local_path="/a.mp4",
            sha256="s",
            rights_status="PROVIDER_LICENSED",
        )
    )
    lib.mark_used("a1", "20260812-use-00000000", scene_id="scene_001")

    entry = lib.get("a1")
    assert entry.use_count == 1
    assert entry.last_used_at is not None
