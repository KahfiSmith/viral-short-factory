"""E2E pipeline integration test (Milestone 14)."""

from __future__ import annotations

from pathlib import Path

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetCandidate, RightsStatus
from viral_shorts_factory.domain.concept import Concept
from viral_shorts_factory.domain.project import ProjectWorkspace
from viral_shorts_factory.domain.script import Beat, Script
from viral_shorts_factory.domain.storyboard import Scene, Storyboard
from viral_shorts_factory.editing.brief import generate_edit_brief, write_edit_brief
from viral_shorts_factory.editing.qc import run_qc
from viral_shorts_factory.editing.video_use_bridge import VideoUseBridge
from viral_shorts_factory.metadata.generator import generate_metadata_files
from viral_shorts_factory.persistence.repositories import DatabaseConnection, ProjectRepository
from viral_shorts_factory.ranking.scoring import CandidateScore, ScoreComponents


def test_full_pipeline_e2e_flow(config: AppConfig, video_fixture: Path):
    # 1. Project scaffold & persistence
    ws = ProjectWorkspace(config)
    project = ws.create("football_comedy", "kiper tarkam neuer")
    project_dir = ws.resolve_project_dir(project.project_id)

    conn = DatabaseConnection(config)
    repo = ProjectRepository(conn)
    repo.create(project)

    # 2. Concept & Script & Storyboard
    concept = Concept(
        project_id=project.project_id,
        title="Kiper Tarkam Neuer",
        premise="Gaya Neuer gagal total.",
        hook="Kiper gaya neuer.",
        comedy_mechanism="expectation_vs_reality",
        payoff="Gagal parah.",
    )
    script = Script(
        target_duration_seconds=28,
        beats=[Beat(id="b1", type="hook", text="Neuer tarkam", estimated_seconds=3.0)],
    )
    scene = Scene(
        scene_id="scene_001",
        order=1,
        purpose="hook",
        target_duration_seconds=3.0,
        spoken_text="Neuer tarkam",
        visual_intent="Goalkeeper action",
        queries=["goalkeeper"],
    )
    storyboard = Storyboard(scenes=[scene])

    # 3. Candidate & Score
    cand = AssetCandidate(
        candidate_id="pexels:100",
        provider="pexels",
        provider_asset_id="100",
        query="goalkeeper",
        rights_status=RightsStatus.PROVIDER_LICENSED,
    )
    score = CandidateScore(
        candidate_id="pexels:100",
        scene_id="scene_001",
        total=0.9,
        components=ScoreComponents(
            query_match=1.0,
            orientation=1.0,
            resolution=1.0,
            duration_fit=1.0,
            source_confidence=0.9,
            duplicate_penalty=0.0,
        ),
    )

    # 4. Edit Brief
    brief_content = generate_edit_brief(
        project, concept, script, storyboard, {"scene_001": (cand, score)}, config
    )
    write_edit_brief(brief_content, project_dir / "edit_brief.md")
    assert (project_dir / "edit_brief.md").is_file()

    # 5. Bridge & Strategy approval
    bridge = VideoUseBridge(config)
    bridge.propose_strategy(project.project_id, "Fast cuts and zoom on reaction.")
    bridge.approve_strategy(project.project_id, "human")

    # 6. QC on final output
    profile = config.profiles["football_comedy"].model_copy(
        update={"min_duration_seconds": 0, "max_duration_seconds": 10}
    )
    qc_report = run_qc(video_fixture, config, profile)
    assert qc_report.passed is True

    # 7. Metadata Generation
    meta = generate_metadata_files(concept, project_dir / "metadata")
    assert meta["title"].is_file()
    assert meta["description"].is_file()
    assert meta["hashtags"].is_file()

    conn.close()
