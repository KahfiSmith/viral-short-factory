"""Pipeline execution context and structured event emission.

Lightweight in Milestone 1: carries the project, config, run id, and a helper
that appends one JSON event line to the project's run log. The orchestrator
arrives in a later milestone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import Project


@dataclass
class PipelineContext:
    """State shared by pipeline stages during one run."""

    project: Project
    config: AppConfig
    workspace_dir: Path
    run_id: str = field(default_factory=lambda: f"run_{uuid4().hex}")
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger("vsf.pipeline")

    @property
    def log_dir(self) -> Path:
        return self.workspace_dir / "logs"

    @property
    def run_log_path(self) -> Path:
        return self.log_dir / "run.jsonl"

    def emit(self, event: str, **metadata: object) -> None:
        """Append one structured event line to the project's run.jsonl."""
        self.logger.info(
            event,
            extra={
                "extra_fields": {
                    "run_id": self.run_id,
                    "project_id": self.project.project_id,
                    "stage": self.project.status.value,
                    "event": event,
                    **metadata,
                }
            },
        )
