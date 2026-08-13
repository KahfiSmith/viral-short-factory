"""Database wrapper + migrations tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from viral_shorts_factory.persistence.db import Database
from viral_shorts_factory.persistence.migrations import MIGRATIONS, apply_migrations


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.sqlite3")
    yield database
    database.close()


def test_migrations_apply_and_schema_version(db: Database) -> None:
    apply_migrations(db)
    rows = db.execute("SELECT version, applied_at FROM schema_version ORDER BY version").fetchall()
    assert [r["version"] for r in rows] == list(range(len(MIGRATIONS)))
    assert all(r["applied_at"] for r in rows)


def test_migrations_idempotent(db: Database) -> None:
    apply_migrations(db)
    apply_migrations(db)  # second run must be a no-op
    rows = db.execute("SELECT COUNT(*) AS n FROM schema_version").fetchone()
    assert rows["n"] == len(MIGRATIONS)


def test_all_tables_exist(db: Database) -> None:
    apply_migrations(db)
    names = {r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {
        "schema_version",
        "projects",
        "pipeline_events",
        "provider_cache",
        "asset_library",
        "asset_usage",
    }
    assert expected <= names


def test_transaction_rolls_back_on_error(db: Database) -> None:
    apply_migrations(db)
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (project_id, schema_version, status, profile, platform,"
                " language, topic, target_duration_seconds, created_at, updated_at)"
                " VALUES ('p1', '1.0', 'INIT', 'p', 'y', 'id', 't', 28, 'now', 'now')"
            )
            raise RuntimeError("boom")
    row = db.execute("SELECT COUNT(*) AS n FROM projects").fetchone()
    assert row["n"] == 0


def test_foreign_keys_enforced(db: Database) -> None:
    apply_migrations(db)
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO pipeline_events (run_id, project_id, from_state, to_state, timestamp)"
                " VALUES ('r1', 'nonexistent', NULL, 'INIT', 'now')"
            )
