"""Tests for video-use bridge and approval policy (Milestone 10)."""

from __future__ import annotations

import json
from pathlib import Path

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import ProjectWorkspace
from viral_shorts_factory.editing.video_use_bridge import VideoUseBridge


def test_video_use_bridge_proposal_flow(config: AppConfig):
    ws = ProjectWorkspace(config)
    project = ws.create("football_comedy", "neuer tarkam")

    project_dir = ws.resolve_project_dir(project.project_id)
    (project_dir / "edit_brief.md").write_text("# Test Brief\n", encoding="utf-8")

    bridge = VideoUseBridge(config)
    handoff_dir = bridge.prepare_handoff(project.project_id)
    assert handoff_dir == project_dir

    proposal = bridge.propose_strategy(project.project_id, "Cut fast and zoom on punchline.")
    assert proposal.status == "PENDING_APPROVAL"

    approved = bridge.approve_strategy(project.project_id, "human")
    assert approved.status == "APPROVED"
    assert approved.approved_by == "human"


def test_bridge_state_machine_matches_docs(config: AppConfig):
    """docs/02 §8: proposal -> AWAITING_EDIT_STRATEGY_APPROVAL, approve -> EDITING."""
    ws = ProjectWorkspace(config)
    project = ws.create("football_comedy", "state check")
    project_dir = ws.resolve_project_dir(project.project_id)
    (project_dir / "edit_brief.md").write_text("# Test Brief\n", encoding="utf-8")

    bridge = VideoUseBridge(config)
    bridge.propose_strategy(project.project_id, "Strategy A")

    with open(project_dir / "project.json", encoding="utf-8") as f:
        after_propose = json.load(f)
    assert after_propose["status"] == "AWAITING_EDIT_STRATEGY_APPROVAL"

    bridge.approve_strategy(project.project_id, "human")

    with open(project_dir / "project.json", encoding="utf-8") as f:
        after_approve = json.load(f)
    assert after_approve["status"] == "EDITING"

    proposal_file: Path = project_dir / "edit" / "proposed_strategy.json"
    assert proposal_file.is_file()
    proposal = json.loads(proposal_file.read_text(encoding="utf-8"))
    assert proposal["status"] == "APPROVED"
    assert proposal["approved_by"] == "human"
