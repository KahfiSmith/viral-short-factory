"""Pipeline runner tests (discovery -> ranking -> download -> approval gate)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import RightsStatus
from viral_shorts_factory.domain.project import ProjectWorkspace
from viral_shorts_factory.domain.states import Stage
from viral_shorts_factory.persistence.repositories import DatabaseConnection, ProjectRepository
from viral_shorts_factory.pipeline.runner import PipelineError, run_pipeline


def run(coro):
    return asyncio.run(coro)


def _prepare_planned_project(config: AppConfig, video_fixture: Path, topic: str = "runner test"):
    """Create a project at ASSET_QUERIES_READY with a local asset registered."""
    from viral_shorts_factory.assets.library import AssetLibrary
    from viral_shorts_factory.domain.storyboard import storyboard_to_json
    from viral_shorts_factory.profiles.football_comedy import (
        build_script_fixture,
        build_storyboard_from_script,
    )

    ws = ProjectWorkspace(config)
    project = ws.create("football_comedy", topic)

    conn = DatabaseConnection(config)
    repo = ProjectRepository(conn)
    repo.create(project)

    # Write script.json + storyboard.json (as vsf plan would).
    project_dir = ws.resolve_project_dir(project.project_id)
    profile = config.profiles["football_comedy"]
    script = build_script_fixture(topic, 28.0)
    storyboard = build_storyboard_from_script(script, profile)
    (project_dir / "script.json").write_text(
        script.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (project_dir / "storyboard.json").write_text(storyboard_to_json(storyboard), encoding="utf-8")

    # Register a local candidate tagged to match the generated queries.
    library = AssetLibrary(conn, config)
    library.register(
        video_fixture,
        tags=["goalkeeper", "football", "soccer"],
        rights_status=RightsStatus.PROVIDER_LICENSED,
    )

    # Advance through creative chain to ASSET_QUERIES_READY.
    chain = [
        Stage.BRIEF_READY,
        Stage.CONCEPT_READY,
        Stage.SCRIPT_READY,
        Stage.STORYBOARD_READY,
        Stage.ASSET_QUERIES_READY,
    ]
    for stage in chain:
        repo.update_status(project.project_id, stage, "run_test")
    conn.close()
    return project.project_id


def test_run_pipeline_reaches_approval_gate(config: AppConfig, video_fixture: Path):
    project_id = _prepare_planned_project(config, video_fixture)
    project, project_dir, message = run(run_pipeline(project_id, config))

    assert project.status == Stage.AWAITING_EDIT_STRATEGY_APPROVAL
    assert message == "awaiting edit strategy approval"

    # Artifacts exist.
    assert (project_dir / "sources").is_dir()
    assert (project_dir / "source_manifest.json").is_file()
    assert (project_dir / "edit_brief.md").is_file()
    assert (project_dir / "edit" / "proposed_strategy.json").is_file()

    manifest = json.loads((project_dir / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["assets"], "manifest must have at least one downloaded asset"

    brief = (project_dir / "edit_brief.md").read_text(encoding="utf-8")
    assert "Edit Brief" in brief

    # Sources downloaded and probed.
    sources = list((project_dir / "sources").glob("*.*"))
    assert sources, "expected downloaded source files"


def test_run_pipeline_requires_queries_ready(config: AppConfig, video_fixture: Path):
    ws = ProjectWorkspace(config)
    project = ws.create("football_comedy", "not planned")
    conn = DatabaseConnection(config)
    try:
        ProjectRepository(conn).create(project)
    finally:
        conn.close()

    with pytest.raises(PipelineError, match="cannot run from state"):
        run(run_pipeline(project.project_id, config))
