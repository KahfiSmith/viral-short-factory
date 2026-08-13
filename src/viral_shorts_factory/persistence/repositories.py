"""Repositories over the SQLite schema.

All writes go through Database.transaction() so a failed update (e.g. an
invalid state transition) rolls back atomically and leaves no partial state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import Project
from viral_shorts_factory.domain.states import Stage, validate_transition
from viral_shorts_factory.persistence.db import Database
from viral_shorts_factory.persistence.migrations import apply_migrations


class RepositoryError(Exception):
    """Raised when a repository operation fails."""


@dataclass(frozen=True)
class CachedResponse:
    """A stored provider response."""

    cache_key: str
    response_json: str
    fetched_at: datetime
    expires_at: datetime
    http_status: int

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass
class AssetLibraryEntry:
    """A row in the local asset library."""

    asset_id: str
    local_path: str
    sha256: str
    rights_status: str = "UNVERIFIED"
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    orientation: str | None = None
    provider: str | None = None
    provider_asset_id: str | None = None
    source_page_url: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None
    use_count: int = 0


@dataclass(frozen=True)
class PipelineEvent:
    """One persisted pipeline transition."""

    run_id: str
    project_id: str
    to_state: Stage
    from_state: Stage | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class DatabaseConnection:
    """Bundles a Database plus migrations applied for a config."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db = Database(config.app.database_path)
        apply_migrations(self.db)

    def close(self) -> None:
        self.db.close()


class ProjectRepository:
    """Projects table mirroring project.json, plus the state machine."""

    def __init__(self, conn: DatabaseConnection) -> None:
        self._db = conn.db

    def create(self, project: Project) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    project_id, schema_version, status, profile, platform, language,
                    topic, target_duration_seconds, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.schema_version,
                    project.status.value,
                    project.profile,
                    project.platform,
                    project.language,
                    project.topic,
                    project.target_duration_seconds,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )

    def get(self, project_id: str) -> Project | None:
        row = self._db.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def list_projects(self) -> list[Project]:
        rows = self._db.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return [p for p in (self._row_to_project(r) for r in rows) if p is not None]

    def update_status(
        self,
        project_id: str,
        to_stage: Stage,
        run_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> Project:
        """Validate the transition, persist status + event atomically."""
        current = self.get(project_id)
        if current is None:
            raise RepositoryError(f"project not found: {project_id}")
        validate_transition(current.status, to_stage)

        timestamp = now or datetime.now(UTC)
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE projects SET status = ?, updated_at = ? WHERE project_id = ?",
                (to_stage.value, timestamp.isoformat(), project_id),
            )
            conn.execute(
                """
                INSERT INTO pipeline_events (
                    run_id, project_id, from_state, to_state, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    current.status.value,
                    to_stage.value,
                    timestamp.isoformat(),
                    json.dumps(metadata or {}),
                ),
            )
        updated = self.get(project_id)
        if updated is None:  # pragma: no cover - row was just written
            raise RepositoryError(f"project vanished during update: {project_id}")
        return updated

    @staticmethod
    def _row_to_project(row: Any) -> Project | None:
        try:
            return Project(
                schema_version=row["schema_version"],
                project_id=row["project_id"],
                status=Stage(row["status"]),
                profile=row["profile"],
                platform=row["platform"],
                language=row["language"],
                topic=row["topic"],
                target_duration_seconds=row["target_duration_seconds"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        except (KeyError, ValueError):
            return None


class EventRepository:
    """Pipeline event log."""

    def __init__(self, conn: DatabaseConnection) -> None:
        self._db = conn.db

    def append(self, event: PipelineEvent) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_events (
                    run_id, project_id, from_state, to_state, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.project_id,
                    event.from_state.value if event.from_state else None,
                    event.to_state.value,
                    event.timestamp.isoformat(),
                    json.dumps(event.metadata),
                ),
            )

    def events_for_project(self, project_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM pipeline_events WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()
        return [dict(row) for row in rows]


class CacheRepository:
    """Provider response cache with TTL."""

    def __init__(self, conn: DatabaseConnection) -> None:
        self._db = conn.db

    def get(self, key: str, now: datetime | None = None) -> CachedResponse | None:
        row = self._db.execute(
            "SELECT * FROM provider_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        cached = CachedResponse(
            cache_key=row["cache_key"],
            response_json=row["response_json"],
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            http_status=row["http_status"],
        )
        if cached.is_expired(now or datetime.now(UTC)):
            return None
        return cached

    def set(
        self,
        key: str,
        response_json: str,
        http_status: int,
        ttl_hours: int,
        now: datetime | None = None,
    ) -> None:
        timestamp = now or datetime.now(UTC)
        expires = datetime.fromtimestamp(timestamp.timestamp() + ttl_hours * 3600, tz=UTC)
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO provider_cache (
                    cache_key, response_json, fetched_at, expires_at, http_status
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = excluded.response_json,
                    fetched_at = excluded.fetched_at,
                    expires_at = excluded.expires_at,
                    http_status = excluded.http_status
                """,
                (key, response_json, timestamp.isoformat(), expires.isoformat(), http_status),
            )

    def delete(self, key: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM provider_cache WHERE cache_key = ?", (key,))

    def purge_expired(self, now: datetime | None = None) -> int:
        timestamp = now or datetime.now(UTC)
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM provider_cache WHERE expires_at <= ?", (timestamp.isoformat(),)
            )
            return cur.rowcount


class AssetLibraryRepository:
    """Local asset library with provenance gate (UNVERIFIED cannot be auto-selected)."""

    def __init__(self, conn: DatabaseConnection) -> None:
        self._db = conn.db

    def register(self, entry: AssetLibraryEntry) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO asset_library (
                    asset_id, local_path, sha256, category, tags, width, height,
                    duration_seconds, orientation, provider, provider_asset_id,
                    source_page_url, rights_status, created_at, last_used_at, use_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.asset_id,
                    entry.local_path,
                    entry.sha256,
                    entry.category,
                    json.dumps(entry.tags),
                    entry.width,
                    entry.height,
                    entry.duration_seconds,
                    entry.orientation,
                    entry.provider,
                    entry.provider_asset_id,
                    entry.source_page_url,
                    entry.rights_status,
                    entry.created_at.isoformat(),
                    entry.last_used_at.isoformat() if entry.last_used_at else None,
                    entry.use_count,
                ),
            )

    def find_by_sha256(self, sha256: str) -> AssetLibraryEntry | None:
        row = self._db.execute("SELECT * FROM asset_library WHERE sha256 = ?", (sha256,)).fetchone()
        return self._row_to_entry(row) if row else None

    def get(self, asset_id: str) -> AssetLibraryEntry | None:
        row = self._db.execute(
            "SELECT * FROM asset_library WHERE asset_id = ?", (asset_id,)
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def search(
        self, *, category: str | None = None, tags: list[str] | None = None
    ) -> list[AssetLibraryEntry]:
        clauses: list[str] = []
        params: list[str] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if tags:
            # Only "?" placeholders are interpolated; tag values are always bound params.
            placeholders = ", ".join("?" for _ in tags)
            clauses.append(
                f"EXISTS (SELECT 1 FROM json_each(tags) WHERE json_each.value IN ({placeholders}))"  # noqa: S608
            )
            params.extend(tags)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""  # noqa: S608
        rows = self._db.execute(
            f"SELECT * FROM asset_library {where} ORDER BY use_count DESC",  # noqa: S608 - fixed literals + "?" only
            tuple(params),
        ).fetchall()
        return [e for e in (self._row_to_entry(r) for r in rows) if e is not None]

    def mark_used(self, asset_id: str, project_id: str, scene_id: str | None = None) -> None:
        now = datetime.now(UTC)
        with self._db.transaction() as conn:
            conn.execute(
                """
                UPDATE asset_library
                SET last_used_at = ?, use_count = use_count + 1
                WHERE asset_id = ?
                """,
                (now.isoformat(), asset_id),
            )
            conn.execute(
                """
                INSERT INTO asset_usage (project_id, asset_id, scene_id, used_at)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, asset_id, scene_id, now.isoformat()),
            )

    @staticmethod
    def _row_to_entry(row: Any) -> AssetLibraryEntry | None:
        try:
            return AssetLibraryEntry(
                asset_id=row["asset_id"],
                local_path=row["local_path"],
                sha256=row["sha256"],
                rights_status=row["rights_status"],
                category=row["category"],
                tags=json.loads(row["tags"]),
                width=row["width"],
                height=row["height"],
                duration_seconds=row["duration_seconds"],
                orientation=row["orientation"],
                provider=row["provider"],
                provider_asset_id=row["provider_asset_id"],
                source_page_url=row["source_page_url"],
                created_at=datetime.fromisoformat(row["created_at"]),
                last_used_at=datetime.fromisoformat(row["last_used_at"])
                if row["last_used_at"]
                else None,
                use_count=row["use_count"],
            )
        except (KeyError, ValueError):
            return None
