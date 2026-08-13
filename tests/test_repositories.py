"""Project/event repository tests: state machine + atomic persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import Project
from viral_shorts_factory.domain.states import InvalidTransitionError, Stage
from viral_shorts_factory.persistence.repositories import (
    DatabaseConnection,
    EventRepository,
    PipelineEvent,
    ProjectRepository,
    RepositoryError,
)


@pytest.fixture()
def conn(tmp_path: Path, config: AppConfig) -> DatabaseConnection:
    config.app.database_path = tmp_path / "test.sqlite3"
    return DatabaseConnection(config)


@pytest.fixture()
def project(conn: DatabaseConnection) -> Project:
    now = datetime(2026, 8, 12, tzinfo=UTC)
    p = Project(
        project_id="20260812-test-00000000",
        profile="football_comedy",
        topic="test",
        target_duration_seconds=28,
        created_at=now,
        updated_at=now,
    )
    ProjectRepository(conn).create(p)
    return p


def test_create_and_get(conn: DatabaseConnection, project: Project) -> None:
    loaded = ProjectRepository(conn).get(project.project_id)
    assert loaded == project
    assert ProjectRepository(conn).get("nope") is None


def test_list_projects(conn: DatabaseConnection, project: Project) -> None:
    projects = ProjectRepository(conn).list_projects()
    assert [p.project_id for p in projects] == [project.project_id]


def test_valid_transition_persists_status_and_event(
    conn: DatabaseConnection, project: Project
) -> None:
    repo = ProjectRepository(conn)
    updated = repo.update_status(project.project_id, Stage.BRIEF_READY, "run_1")
    assert updated.status == Stage.BRIEF_READY
    assert updated.updated_at >= project.updated_at

    events = EventRepository(conn).events_for_project(project.project_id)
    assert len(events) == 1
    assert events[0]["from_state"] == "INIT"
    assert events[0]["to_state"] == "BRIEF_READY"
    assert events[0]["run_id"] == "run_1"


def test_forbidden_transition_raises_and_rolls_back(
    conn: DatabaseConnection, project: Project
) -> None:
    repo = ProjectRepository(conn)
    with pytest.raises(InvalidTransitionError):
        repo.update_status(project.project_id, Stage.COMPLETE, "run_1")

    # Nothing persisted: status unchanged, no event row.
    assert repo.get(project.project_id).status == Stage.INIT
    assert EventRepository(conn).events_for_project(project.project_id) == []


def test_update_missing_project_raises(conn: DatabaseConnection) -> None:
    with pytest.raises(RepositoryError, match="not found"):
        ProjectRepository(conn).update_status("nope", Stage.BRIEF_READY, "run_1")


def test_append_event_direct(conn: DatabaseConnection, project: Project) -> None:
    EventRepository(conn).append(
        PipelineEvent(
            run_id="run_x",
            project_id=project.project_id,
            to_state=Stage.ASSETS_SELECTED,
            from_state=Stage.STORYBOARD_READY,
            metadata={"count": 3},
        )
    )
    events = EventRepository(conn).events_for_project(project.project_id)
    assert len(events) == 1
    assert events[0]["metadata"] == '{"count": 3}'
