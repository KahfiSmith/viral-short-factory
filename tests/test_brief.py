"""Tests for edit brief generation (Milestone 9)."""

from __future__ import annotations

from datetime import UTC, datetime

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetCandidate, RightsStatus
from viral_shorts_factory.domain.concept import Concept
from viral_shorts_factory.domain.project import Project
from viral_shorts_factory.domain.script import Beat, Script
from viral_shorts_factory.domain.storyboard import Scene, Storyboard
from viral_shorts_factory.editing.brief import generate_edit_brief
from viral_shorts_factory.ranking.scoring import CandidateScore, ScoreComponents


def test_generate_edit_brief(config: AppConfig):
    now = datetime.now(UTC)
    project = Project(
        project_id="20260812-test-12345678",
        profile="football_comedy",
        topic="Test topic",
        target_duration_seconds=28,
        created_at=now,
        updated_at=now,
    )
    concept = Concept(
        project_id=project.project_id,
        title="Test Title",
        premise="Test Premise",
        hook="Test Hook",
        comedy_mechanism="expectation_vs_reality",
        payoff="Test Payoff",
    )
    script = Script(
        target_duration_seconds=28,
        beats=[Beat(id="b1", type="hook", text="Test Hook Text", estimated_seconds=3.0)],
    )
    scene = Scene(
        scene_id="scene_001",
        order=1,
        purpose="hook",
        target_duration_seconds=3.0,
        spoken_text="Test Hook Text",
        visual_intent="Test visual intent",
        queries=["test query"],
    )
    storyboard = Storyboard(scenes=[scene])

    cand = AssetCandidate(
        candidate_id="pexels:100",
        provider="pexels",
        provider_asset_id="100",
        query="test query",
        rights_status=RightsStatus.PROVIDER_LICENSED,
    )
    score = CandidateScore(
        candidate_id="pexels:100",
        scene_id="scene_001",
        total=0.85,
        components=ScoreComponents(
            query_match=0.8,
            orientation=1.0,
            resolution=1.0,
            duration_fit=0.9,
            source_confidence=0.9,
            duplicate_penalty=0.0,
        ),
    )

    brief_text = generate_edit_brief(
        project, concept, script, storyboard, {"scene_001": (cand, score)}, config
    )

    assert "# Edit Brief: Test Title" in brief_text
    assert "sources/scene_001_pexels_100.mp4" in brief_text
    assert "Expectation vs Reality" in brief_text
