"""Provider cache TTL tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.persistence.repositories import CacheRepository, DatabaseConnection

FIXED_NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def repo(tmp_path: Path, config: AppConfig) -> CacheRepository:
    config.app.database_path = tmp_path / "cache.sqlite3"
    return CacheRepository(DatabaseConnection(config))


def test_cache_hit_before_expiry(repo: CacheRepository) -> None:
    repo.set("k1", '{"ok": true}', 200, ttl_hours=24, now=FIXED_NOW)
    cached = repo.get("k1", now=FIXED_NOW + timedelta(hours=23))
    assert cached is not None
    assert cached.response_json == '{"ok": true}'
    assert cached.http_status == 200


def test_cache_miss_after_expiry(repo: CacheRepository) -> None:
    repo.set("k1", '{"ok": true}', 200, ttl_hours=24, now=FIXED_NOW)
    assert repo.get("k1", now=FIXED_NOW + timedelta(hours=24)) is None
    assert repo.get("k1", now=FIXED_NOW + timedelta(days=2)) is None


def test_cache_miss_for_unknown_key(repo: CacheRepository) -> None:
    assert repo.get("nope", now=FIXED_NOW) is None


def test_set_overwrites_existing(repo: CacheRepository) -> None:
    repo.set("k1", "v1", 200, ttl_hours=24, now=FIXED_NOW)
    repo.set("k1", "v2", 500, ttl_hours=1, now=FIXED_NOW)
    cached = repo.get("k1", now=FIXED_NOW + timedelta(minutes=30))
    assert cached is not None
    assert cached.response_json == "v2"
    assert cached.http_status == 500


def test_purge_expired(repo: CacheRepository) -> None:
    repo.set("stale", "a", 200, ttl_hours=1, now=FIXED_NOW)
    repo.set("fresh", "b", 200, ttl_hours=24, now=FIXED_NOW)
    now = FIXED_NOW + timedelta(hours=2)
    removed = repo.purge_expired(now=now)
    assert removed == 1
    assert repo.get("stale", now=now) is None
    assert repo.get("fresh", now=now) is not None


def test_delete(repo: CacheRepository) -> None:
    repo.set("k1", "v", 200, ttl_hours=24, now=FIXED_NOW)
    repo.delete("k1")
    assert repo.get("k1", now=FIXED_NOW) is None
