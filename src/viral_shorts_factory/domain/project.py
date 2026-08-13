"""Project model, ID generation, and workspace creation."""

from __future__ import annotations

import json
import re
import secrets
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.states import Stage

SCHEMA_VERSION = "1.0"
PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-\s]+$")

# Subdirectories every project workspace gets.
WORKSPACE_DIRS = ("sources", "metadata", "logs", "edit")


class WorkspaceError(Exception):
    """Raised when a project workspace cannot be created or loaded."""


def _slugify(topic: str) -> str:
    """Turn a topic into a clean lowercase slug (spaces -> hyphens or direct words)."""
    normalized = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode("ascii")
    words = [w for w in re.split(r"[^a-zA-Z0-9]+", normalized.lower()) if w]
    if not words:
        words = ["project"]
    return "-".join(words)


def generate_project_id(topic: str, now: datetime | None = None) -> str:
    """Generate a clean project id directly from topic (e.g. 'betta fish' -> 'betta-fish')."""
    return _slugify(topic)


class Project(BaseModel):
    """Persisted project metadata (schema_version 1.0)."""

    schema_version: str = SCHEMA_VERSION
    project_id: str
    status: Stage = Stage.INIT
    profile: str
    platform: str = "youtube_shorts"
    language: str = "id-ID"
    topic: str
    target_duration_seconds: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    def to_json(self) -> str:
        """Serialize to JSON with a stable ordering."""
        return self.model_dump_json(indent=2) + "\n"


def load_project(project_dir: Path) -> Project:
    """Load and validate a project.json from a workspace directory."""
    project_file = project_dir / "project.json"
    if not project_file.is_file():
        raise WorkspaceError(f"project.json not found in {project_dir}")
    try:
        raw = json.loads(project_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"invalid JSON in {project_file}: {exc}") from exc
    try:
        return Project.model_validate(raw)
    except Exception as exc:
        raise WorkspaceError(f"invalid project.json in {project_file}: {exc}") from exc


def _atomic_write(path: Path, content: str) -> None:
    """Write a file atomically (temp file in the same dir, then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        tmp_path = Path(tmp_name)
        tmp_path.replace(path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


class ProjectWorkspace:
    """Creates and inspects project workspaces under a configured root."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.project_root = config.app.project_root.expanduser().resolve()

    def _ensure_outside_repo(self, target: Path) -> None:
        """Reject workspaces that would land inside the VSF source repository."""
        repo_root = Path(__file__).resolve().parents[3]
        try:
            target.relative_to(repo_root)
        except ValueError:
            return
        raise WorkspaceError(
            f"project workspace {target} must not be created inside the source repository "
            f"({repo_root})"
        )

    def resolve_project_dir(self, project_id: str) -> Path:
        """Absolute path of a project workspace by id."""
        if not PROJECT_ID_RE.match(project_id):
            raise WorkspaceError(f"invalid project id format: {project_id!r}")
        return self.project_root / project_id

    def create(
        self,
        profile: str,
        topic: str,
        *,
        platform: str | None = None,
        language: str | None = None,
        target_duration_seconds: int | None = None,
        now: datetime | None = None,
    ) -> Project:
        """Create a new project workspace. Refuses to overwrite an existing id."""
        timestamp = now or datetime.now(UTC)
        defaults = self.config.defaults
        project = Project(
            project_id=generate_project_id(topic, now=timestamp),
            profile=profile,
            platform=platform or defaults.platform,
            language=language or defaults.language,
            topic=topic,
            target_duration_seconds=target_duration_seconds or 28,
            created_at=timestamp,
            updated_at=timestamp,
        )

        project_dir = self.resolve_project_dir(project.project_id)
        self._ensure_outside_repo(project_dir)
        if project_dir.exists():
            raise WorkspaceError(f"project already exists: {project_dir}")

        project_dir.mkdir(parents=True)
        for name in WORKSPACE_DIRS:
            (project_dir / name).mkdir()
        _atomic_write(project_dir / "project.json", project.to_json())
        return project

    def load(self, project_id: str) -> tuple[Project, Path]:
        """Load a project by id, returning (project, workspace_dir)."""
        project_dir = self.resolve_project_dir(project_id)
        if not project_dir.is_dir():
            raise WorkspaceError(f"project not found: {project_id} (looked in {self.project_root})")
        return load_project(project_dir), project_dir
