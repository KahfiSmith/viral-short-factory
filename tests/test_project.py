"""Project model and workspace tests."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import (
    PROJECT_ID_RE,
    Project,
    ProjectWorkspace,
    WorkspaceError,
    generate_project_id,
    load_project,
)
from viral_shorts_factory.domain.states import Stage

FIXED_NOW = datetime(2026, 8, 12, 5, 45, 0, tzinfo=UTC)


def test_project_id_format() -> None:
    pid = generate_project_id("Kiper Tarkam Merasa Dirinya Neuer", now=FIXED_NOW)
    assert PROJECT_ID_RE.match(pid)
    assert pid == "kiper-tarkam-merasa-dirinya-neuer"


def test_project_id_slug_empty_topic() -> None:
    pid = generate_project_id("  ", now=FIXED_NOW)
    assert pid == "project"


def test_workspace_created_outside_repo(config: AppConfig, tmp_path: Path) -> None:
    config.app.project_root = tmp_path / "projects"
    workspace = ProjectWorkspace(config)
    project = workspace.create(profile="football_comedy", topic="kiper merasa neuer", now=FIXED_NOW)

    project_dir = workspace.resolve_project_dir(project.project_id)
    assert project_dir.is_dir()
    assert (project_dir / "sources").is_dir()
    assert (project_dir / "metadata").is_dir()
    assert (project_dir / "logs").is_dir()
    assert (project_dir / "edit").is_dir()

    project_file = project_dir / "project.json"
    assert project_file.is_file()
    raw = json.loads(project_file.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "1.0"
    assert raw["status"] == "INIT"
    assert raw["project_id"] == project.project_id


def test_workspace_inside_source_repo_rejected(config: AppConfig) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config.app.project_root = repo_root
    workspace = ProjectWorkspace(config)
    with pytest.raises(WorkspaceError, match="inside the source repository"):
        workspace.create(profile="football_comedy", topic="should fail", now=FIXED_NOW)


def test_duplicate_project_id_refused(
    config: AppConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config.app.project_root = tmp_path / "projects"
    # Force a deterministic id suffix so the second create collides.
    # token_hex(n) returns 2*n hex chars; keep the 8-char suffix shape.
    monkeypatch.setattr(
        "viral_shorts_factory.domain.project.secrets.token_hex", lambda n: "0" * (2 * n)
    )
    workspace = ProjectWorkspace(config)
    workspace.create(profile="football_comedy", topic="same topic", now=FIXED_NOW)
    with pytest.raises(WorkspaceError, match="already exists"):
        workspace.create(profile="football_comedy", topic="same topic", now=FIXED_NOW)


def test_load_project_roundtrip(config: AppConfig, tmp_path: Path) -> None:
    config.app.project_root = tmp_path / "projects"
    workspace = ProjectWorkspace(config)
    created = workspace.create(profile="football_comedy", topic="roundtrip", now=FIXED_NOW)

    loaded, project_dir = workspace.load(created.project_id)
    assert loaded == created
    assert project_dir == workspace.resolve_project_dir(created.project_id)


def test_load_project_invalid_json(tmp_path: Path) -> None:
    project_dir = tmp_path / "p"
    project_dir.mkdir()
    (project_dir / "project.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="invalid JSON"):
        load_project(project_dir)


def test_load_missing_project(config: AppConfig, tmp_path: Path) -> None:
    config.app.project_root = tmp_path / "projects"
    workspace = ProjectWorkspace(config)
    with pytest.raises(WorkspaceError, match="not found"):
        workspace.load("20260812-nope-00000000")


def test_project_json_is_stable_and_valid() -> None:
    project = Project(
        project_id="20260812-test-00000000",
        profile="football_comedy",
        topic="test",
        target_duration_seconds=28,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    assert project.status == Stage.INIT
    data = json.loads(project.to_json())
    assert data["schema_version"] == "1.0"
    assert data["project_id"] == "20260812-test-00000000"
    assert data["status"] == "INIT"
    assert re.fullmatch(r".+", data["created_at"])
