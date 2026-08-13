"""Pixabay provider contract tests (mocked HTTP + tmp SQLite cache)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetSearchRequest, RightsStatus
from viral_shorts_factory.persistence.repositories import CacheRepository, DatabaseConnection
from viral_shorts_factory.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)
from viral_shorts_factory.providers.pixabay import PixabayProvider, ProviderConfigError

FIXED_NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def _video(
    vid: int,
    *,
    width: int = 1080,
    height: int = 1920,
    duration: int = 8,
    files: dict[str, tuple[int, int, str]] | None = None,
) -> dict:
    """Build a raw Pixabay video hit."""
    if files is None:
        files = {
            "large": (1080, 1920, "https://pixabay.com/large.mp4"),
            "medium": (540, 960, "https://pixabay.com/medium.mp4"),
        }
    return {
        "id": vid,
        "pageURL": f"https://pixabay.com/videos/{vid}/",
        "duration": duration,
        "image": f"https://pixabay.com/preview_{vid}.jpg",
        "user": "Test Pixabay User",
        "userImageURL": f"https://pixabay.com/user_{vid}.jpg",
        "tags": "goalkeeper, soccer",
        "videos": {
            quality: {
                "type": "video/mp4",
                "url": url,
                "width": w,
                "height": h,
                "size": 100000 + vid,
            }
            for quality, (w, h, url) in files.items()
        },
    }


def _search_response(*videos: dict) -> dict:
    return {"total": len(videos), "totalHits": len(videos), "hits": list(videos)}


def _provider(
    handler, config: AppConfig, *, cache_ttl_hours: int = 24
) -> tuple[PixabayProvider, CacheRepository]:
    conn = DatabaseConnection(config)
    cache = CacheRepository(conn)
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    provider = PixabayProvider(
        "test-key-123", cache, client, per_page=20, cache_ttl_hours=cache_ttl_hours
    )
    return provider, cache


def _request() -> AssetSearchRequest:
    return AssetSearchRequest(
        scene_id="scene_001", query="goalkeeper confident", minimum_height=1080
    )


def test_search_normalizes_candidates(config: AppConfig, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_response(_video(111), _video(222)))

    provider, _ = _provider(handler, config)
    candidates = run(provider.search(_request()))

    assert len(candidates) == 2
    first = candidates[0]
    assert first.candidate_id == "pixabay:111"
    assert first.provider == "pixabay"
    assert first.provider_asset_id == "111"
    assert first.source_page_url == "https://pixabay.com/videos/111/"
    assert first.preview_url == "https://pixabay.com/preview_111.jpg"
    assert first.width == 1080 and first.height == 1920
    assert first.duration_seconds == 8.0
    assert first.tags == ["goalkeeper", "soccer"]
    assert first.contributor_name == "Test Pixabay User"
    assert first.query == "goalkeeper confident"
    assert first.rights_status == RightsStatus.PROVIDER_LICENSED
    assert first.raw_metadata_hash.startswith("sha256:")
    assert [v.height for v in first.download_variants] == [1920, 960]


def test_key_and_query_params(config: AppConfig, tmp_path: Path) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_response(_video(111)))

    provider, _ = _provider(handler, config)
    run(provider.search(_request()))

    assert captured["params"]["key"] == "test-key-123"
    assert captured["params"]["q"] == "goalkeeper confident"
    assert captured["params"]["safesearch"] == "true"
    assert captured["params"]["order"] == "popular"
    assert captured["params"]["category"] == "sports"
    assert captured["params"]["lang"] == "en-US"


def test_minimum_height_filtered(config: AppConfig, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_search_response(
                _video(111, height=1920),
                _video(222, height=720, files={"small": (540, 720, "u.mp4")}),
            ),
        )

    provider, _ = _provider(handler, config)
    candidates = run(provider.search(_request()))
    assert [c.provider_asset_id for c in candidates] == ["111"]


def test_missing_mp4_variant_skipped(config: AppConfig, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        no_mp4 = _video(333)
        no_mp4["videos"] = {
            "small": {"type": "video/webm", "url": "x.webm", "width": 540, "height": 960}
        }
        return httpx.Response(200, json=_search_response(_video(111), no_mp4))

    provider, _ = _provider(handler, config)
    candidates = run(provider.search(_request()))
    assert [c.provider_asset_id for c in candidates] == ["111"]


def test_cache_hit_within_24h_no_network(config: AppConfig, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_search_response(_video(111)))

    provider, _ = _provider(handler, config)

    # First call -> network.
    first = run(provider.search(_request()))
    assert calls["n"] == 1
    assert len(first) == 1

    # Second call 1 hour later -> cache hit, zero network.
    second = run(provider.search(_request()))
    assert calls["n"] == 1  # no additional request
    assert second == first


def test_cache_miss_after_24h_refetches(config: AppConfig, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_search_response(_video(111)))

    provider, _ = _provider(handler, config)
    run(provider.search(_request()))
    assert calls["n"] == 1

    # Force the stored entry to be long-expired (real now is later), then search again.
    from viral_shorts_factory.persistence.db import Database

    database = Database(config.app.database_path)
    with database.transaction() as conn:
        conn.execute(
            "UPDATE provider_cache SET expires_at = ?",
            ("2000-01-01T00:00:00+00:00",),
        )
    database.close()

    run(provider.search(_request()))
    assert calls["n"] == 2  # network again (cache expired)


def test_cache_only_stores_200(config: AppConfig, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={})

    provider, _ = _provider(handler, config)
    # Always-500 -> retries exhaust -> error, and nothing is cached.
    with pytest.raises(ProviderServerError):
        run(provider.search(_request()))
    assert calls["n"] == 3

    # A later successful search must hit the network again (nothing was cached).
    ok_calls = {"n": 0}

    def ok_handler(request: httpx.Request) -> httpx.Response:
        ok_calls["n"] += 1
        return httpx.Response(200, json=_search_response(_video(111)))

    provider2, _ = _provider(ok_handler, config)
    candidates = run(provider2.search(_request()))
    assert ok_calls["n"] == 1  # network was hit (cache empty)
    assert len(candidates) == 1


def test_retry_on_5xx_then_success(config: AppConfig, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json=_search_response(_video(111)))

    provider, _ = _provider(handler, config)
    candidates = run(provider.search(_request()))
    assert calls["n"] == 2
    assert len(candidates) == 1


def test_retry_on_429_then_success(config: AppConfig, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={})
        return httpx.Response(200, json=_search_response(_video(111)))

    provider, _ = _provider(handler, config)
    candidates = run(provider.search(_request()))
    assert calls["n"] == 2
    assert len(candidates) == 1


def test_401_raises_auth_error_no_retry(config: AppConfig, tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={})

    provider, _ = _provider(handler, config)
    with pytest.raises(ProviderAuthError):
        run(provider.search(_request()))
    assert calls["n"] == 1


def test_rate_limit_exhausted_raises(config: AppConfig, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    provider, _ = _provider(handler, config)
    with pytest.raises(ProviderRateLimitError):
        run(provider.search(_request()))


def test_corrupt_response_raises(config: AppConfig, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not json")

    provider, _ = _provider(handler, config)
    with pytest.raises(ProviderResponseError):
        run(provider.search(_request()))


def test_key_missing_from_config_raises(config: AppConfig, tmp_path: Path) -> None:
    conn = DatabaseConnection(config)
    try:
        with pytest.raises(ProviderConfigError, match="pixabay API key not set"):
            PixabayProvider.from_config(config, conn, env={})
    finally:
        conn.close()


def test_cache_key_stable_across_param_order() -> None:
    a = PixabayProvider._cache_key({"q": "x", "order": "popular", "safesearch": "true"})
    b = PixabayProvider._cache_key({"safesearch": "true", "q": "x", "order": "popular"})
    assert a == b
    assert a != PixabayProvider._cache_key({"q": "y", "order": "popular", "safesearch": "true"})


def test_no_network_all_mocked(config: AppConfig, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "pixabay.com"
        return httpx.Response(200, json=_search_response(_video(1)))

    provider, _ = _provider(handler, config)
    run(provider.search(_request()))
