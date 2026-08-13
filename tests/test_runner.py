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


def test_search_provider_accumulates_video_and_image_results() -> None:
    from viral_shorts_factory.domain.assets import AssetCandidate, AssetSearchRequest, MediaType
    from viral_shorts_factory.pipeline.runner import _search_provider

    class FakeProvider:
        name = "fake"

        async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
            return [
                AssetCandidate(
                    candidate_id=f"fake:{request.media_type.value}",
                    provider=self.name,
                    provider_asset_id=request.media_type.value,
                    media_type=request.media_type,
                    query=request.query,
                    rights_status=RightsStatus.PROVIDER_LICENSED,
                )
            ]

    requests = [
        AssetSearchRequest(scene_id="scene_001", query="betta fish", media_type=MediaType.VIDEO),
        AssetSearchRequest(scene_id="scene_001", query="betta fish", media_type=MediaType.IMAGE),
    ]

    found = run(_search_provider(FakeProvider(), requests))

    assert [candidate.media_type for candidate in found["scene_001"]] == [
        MediaType.VIDEO,
        MediaType.IMAGE,
    ]


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


def test_materialize_unique_asset_deduplicates_cross_provider_bytes(
    config: AppConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from viral_shorts_factory.assets.downloader import DownloadedAsset
    from viral_shorts_factory.assets.probe import ProbeResult
    from viral_shorts_factory.domain.assets import AssetCandidate
    from viral_shorts_factory.pipeline import runner as pipeline_runner

    calls: list[str] = []
    first_path = tmp_path / "sources" / "scene_001_pexels_1.mp4"
    second_path = tmp_path / "assets" / "scene_001_pixabay_2.mp4"
    probe = ProbeResult(
        duration_seconds=5.0,
        width=1080,
        height=1920,
        fps=30.0,
        video_codec="h264",
        has_audio=False,
    )

    def fake_materialize(candidate, _scene_id, destination_dir, _downloader, _library):
        calls.append(candidate.candidate_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        path = first_path if candidate.provider == "pexels" else second_path
        path.write_bytes(b"same video bytes")
        return DownloadedAsset(
            asset_id=f"asset_{candidate.provider}",
            candidate_id=candidate.candidate_id,
            local_path=str(path),
            sha256="same-sha256",
            bytes=17,
            probe=probe,
        )

    monkeypatch.setattr(pipeline_runner, "_materialize_asset", fake_materialize)
    pexels = AssetCandidate(
        candidate_id="pexels:1",
        provider="pexels",
        provider_asset_id="1",
        query="fish",
        rights_status="PROVIDER_LICENSED",
    )
    pixabay = AssetCandidate(
        candidate_id="pixabay:2",
        provider="pixabay",
        provider_asset_id="2",
        query="fish",
        rights_status="PROVIDER_LICENSED",
    )
    by_candidate = {}
    by_sha256 = {}

    first = pipeline_runner._materialize_unique_asset(
        pexels, "scene_001", first_path.parent, None, None, by_candidate, by_sha256
    )
    second = pipeline_runner._materialize_unique_asset(
        pixabay, "scene_001", second_path.parent, None, None, by_candidate, by_sha256
    )

    assert calls == ["pexels:1", "pixabay:2"]
    assert second.asset_id == first.asset_id
    assert second.local_path == first.local_path
    assert first_path.is_file()
    assert not second_path.exists()


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
