"""video-use editing engine bridge (docs/02 §7-8, docs/05 M10)."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import ProjectWorkspace
from viral_shorts_factory.domain.states import Stage


class BridgeError(Exception):
    """Raised when bridge operations fail."""


class EditStrategyProposal(BaseModel):
    """Proposed editing strategy by video-use (docs/03 §10)."""

    schema_version: str = "1.0"
    strategy_id: str
    project_id: str
    strategy_text: str
    status: str = "PENDING_APPROVAL"
    created_at: str
    approved_at: str | None = None
    approved_by: str | None = None


class VideoUseBridge:
    """Orchestrates handoff and strategy approval boundary with upstream video-use."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.repo_path = config.video_use.repo_path.expanduser().resolve()

    def verify_upstream(self) -> bool:
        """Verify the upstream video-use repository path exists."""
        return self.repo_path.exists() and self.repo_path.is_dir()

    def prepare_handoff(self, project_id: str) -> Path:
        """Ensure project workspace is prepared with sources/ and edit_brief.md."""
        ws = ProjectWorkspace(self.config)
        _, project_dir = ws.load(project_id)

        sources_dir = project_dir / "sources"
        brief_file = project_dir / "edit_brief.md"

        if not sources_dir.exists():
            raise BridgeError(f"sources directory missing in project {project_id}")
        if not brief_file.exists():
            raise BridgeError(f"edit_brief.md missing in project {project_id}")

        return project_dir

    def propose_strategy(
        self,
        project_id: str,
        strategy_text: str,
        now: datetime | None = None,
    ) -> EditStrategyProposal:
        """Create and persist an edit strategy proposal."""
        ws = ProjectWorkspace(self.config)
        project, project_dir = ws.load(project_id)

        timestamp = (now or datetime.now(UTC)).isoformat()
        proposal = EditStrategyProposal(
            strategy_id=f"strategy_{secrets.token_hex(8)}",
            project_id=project_id,
            strategy_text=strategy_text,
            status="PENDING_APPROVAL",
            created_at=timestamp,
        )

        proposal_file = project_dir / "edit" / "proposed_strategy.json"
        proposal_file.parent.mkdir(parents=True, exist_ok=True)
        proposal_file.write_text(proposal.model_dump_json(indent=2) + "\n", encoding="utf-8")

        # A proposal exists -> the pipeline is now waiting for human approval
        # (docs/02 §8: EDIT_STRATEGY_PROPOSED -> AWAITING_EDIT_STRATEGY_APPROVAL).
        project.status = Stage.AWAITING_EDIT_STRATEGY_APPROVAL
        project.updated_at = now or datetime.now(UTC)
        (project_dir / "project.json").write_text(project.to_json(), encoding="utf-8")

        return proposal

    def approve_strategy(
        self,
        project_id: str,
        approver: str = "human",
        now: datetime | None = None,
    ) -> EditStrategyProposal:
        """Approve proposed strategy and advance pipeline stage."""
        ws = ProjectWorkspace(self.config)
        project, project_dir = ws.load(project_id)

        proposal_file = project_dir / "edit" / "proposed_strategy.json"
        if not proposal_file.is_file():
            raise BridgeError(f"no strategy proposal found for project {project_id}")

        proposal = EditStrategyProposal.model_validate(
            json.loads(proposal_file.read_text(encoding="utf-8"))
        )

        timestamp = (now or datetime.now(UTC)).isoformat()
        proposal.status = "APPROVED"
        proposal.approved_at = timestamp
        proposal.approved_by = approver

        proposal_file.write_text(proposal.model_dump_json(indent=2) + "\n", encoding="utf-8")

        # Approved -> editing may begin (docs/02 §8: AWAITING_EDIT_STRATEGY_APPROVAL -> EDITING).
        project.status = Stage.EDITING
        project.updated_at = now or datetime.now(UTC)
        (project_dir / "project.json").write_text(project.to_json(), encoding="utf-8")

        return proposal
