"""Schema migrations.

Each migration is an ordered SQL string. ``apply_migrations`` tracks applied
versions in the ``schema_version`` table and applies each pending migration in
its own transaction, so a failure never leaves a partial schema.
"""

from __future__ import annotations

from datetime import UTC, datetime

from viral_shorts_factory.persistence.db import Database

MIGRATIONS: list[str] = [
    # 0: projects
    """
    CREATE TABLE projects (
        project_id TEXT PRIMARY KEY,
        schema_version TEXT NOT NULL,
        status TEXT NOT NULL,
        profile TEXT NOT NULL,
        platform TEXT NOT NULL,
        language TEXT NOT NULL,
        topic TEXT NOT NULL,
        target_duration_seconds INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    # 1: pipeline_events
    """
    CREATE TABLE pipeline_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        from_state TEXT,
        to_state TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}'
    );
    """,
    # 2: provider_cache
    """
    CREATE TABLE provider_cache (
        cache_key TEXT PRIMARY KEY,
        response_json TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        http_status INTEGER NOT NULL
    );
    """,
    # 3: asset_library
    """
    CREATE TABLE asset_library (
        asset_id TEXT PRIMARY KEY,
        local_path TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        category TEXT,
        tags TEXT NOT NULL DEFAULT '[]',
        width INTEGER,
        height INTEGER,
        duration_seconds REAL,
        orientation TEXT,
        provider TEXT,
        provider_asset_id TEXT,
        source_page_url TEXT,
        rights_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
        created_at TEXT NOT NULL,
        last_used_at TEXT,
        use_count INTEGER NOT NULL DEFAULT 0
    );
    """,
    # 4: asset_usage
    """
    CREATE TABLE asset_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        asset_id TEXT NOT NULL REFERENCES asset_library(asset_id),
        scene_id TEXT,
        used_at TEXT NOT NULL
    );
    """,
    # 5: sha256 index for duplicate detection
    """
    CREATE INDEX IF NOT EXISTS idx_asset_sha256 ON asset_library(sha256);
    """,
]


def apply_migrations(db: Database) -> None:
    """Create the schema_version table and apply all pending migrations."""
    with db.transaction() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )

    applied = {row["version"] for row in db.execute("SELECT version FROM schema_version")}

    for index, migration in enumerate(MIGRATIONS):
        if index in applied:
            continue
        with db.transaction() as conn:
            conn.executescript(migration)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (index, datetime.now(UTC).isoformat()),
            )
