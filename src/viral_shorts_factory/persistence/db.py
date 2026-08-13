"""SQLite connection wrapper with transactional support.

Uses the stdlib sqlite3 module. Connections are per-database-path, opened with
foreign keys enabled; writes go through the transaction context manager so a
failed operation rolls back atomically.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    """Owning wrapper around a single SQLite database file."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block inside a transaction; roll back on any exception."""
        try:
            yield self._conn
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """Run a single statement outside an explicit transaction."""
        return self._conn.execute(sql, params)
