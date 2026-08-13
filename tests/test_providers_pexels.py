"""Pexels provider contract tests (mocked HTTP via httpx MockTransport)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetSearchRequest, RightsStatus
from viral_shorts_factory.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)
from viral_shorts_factory.providers.pexels import PexelsProvider, ProviderConfigError


def run(coro):
    return asyncio.run(coro)


def _video(
    vid: int,
    *,
    width: int = 1080,
    height: int = 1920,
    duration: float = 8.4,
    files: list[tuple[str, int, int]] | None = None,
) -> dict:
    """Build a raw Pexels video item."""
    if files is None:
        files = [("hd", 1080, 1920), ("sd", 540, 960)]
    return {
        "id": vid,
        "width": width,
        "height": height,
        "duration": duration,
        "url": f"https://www.pexels.com/video/{vid}/",
        "image": f"https://images.pexels.com/videos/{vid}/preview.jpg",
        "video_files": [
            {
                "id": 1000 + vid,
                "quality": q,
                "file_type": "video/mp4",
                "width": w,
                "height": h,
                "link": f"https://videos.pexels.com/{vid}-{q}.mp4",
            }
            for q, w, h in files
        ],
        "user": {"id": 99, "name": "Test Contributor", "url": "https://www.pexels.com/@test"},
    }


def _search_response(*videos: dict) -> dict:
    return {"page": 1, "per_page": 20, "total_results": len(videos), "videos": list(videos)}


def _provider(handler) -> PexelsProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return PexelsProvider("test-key-123", client, per_page=20, max_attempts=3)


def _request() -> AssetSearchRequest:
    return AssetSearchRequest(
        scene_id="scene_001", query="goalkeeper confident", minimum_height=1080
    )


def test_search_normalizes_candidates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_search_response(_video(111), _video(222)))

    provider = _provider(handler)
    candidates = run(provider.search(_request()))

    assert len(candidates) == 2
    first = candidates[0]
    assert first.candidate_id == "pexels:111"
    assert first.provider == "pexels"
    assert first.provider_asset_id == "111"
    assert first.source_page_url == "https://www.pexels.com/video/111/"
    assert first.preview_url is not None
    assert first.width == 1080 and first.height == 1920
    assert first.duration_seconds == 8.4
    assert first.contributor_name == "Test Contributor"
    assert first.query == "goalkeeper confident"
    assert first.rights_status == RightsStatus.PROVIDER_LICENSED
    assert first.raw_metadata_hash.startswith("sha256:")
    # Variants sorted by height desc, mp4 only.
    assert [v.height for v in first.download_variants] == [1920, 960]
    assert all(v.file_type == "video/mp4" for v in first.download_variants)


def test_auth_header_and_query_params() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_search_response(_video(111)))

    provider = _provider(handler)
    run(provider.search(_request()))

    assert captured["auth"] == "test-key-123"
    assert captured["params"]["orientation"] == "portrait"
    assert captured["params"]["size"] == "medium"
    assert captured["params"]["locale"] == "en-US"
    assert captured["params"]["query"] == "goalkeeper confident"


def test_minimum_height_filtered() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_search_response(
                _video(111, height=1920),  # keep (best variant 1920)
                _video(222, height=720, files=[("sd", 540, 720)]),  # best variant 720 -> drop
            ),
        )

    provider = _provider(handler)
    candidates = run(provider.search(_request()))
    assert [c.provider_asset_id for c in candidates] == ["111"]


def test_missing_mp4_variant_skipped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        no_mp4 = _video(333)
        no_mp4["video_files"] = [
            {
                "id": 1,
                "quality": "sd",
                "file_type": "video/webm",
                "width": 540,
                "height": 960,
                "link": "x.webm",
            }
        ]
        return httpx.Response(200, json=_search_response(_video(111), no_mp4))

    provider = _provider(handler)
    candidates = run(provider.search(_request()))
    assert [c.provider_asset_id for c in candidates] == ["111"]


def test_retry_on_429_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={})
        return httpx.Response(200, json=_search_response(_video(111)))

    provider = _provider(handler)
    candidates = run(provider.search(_request()))
    assert calls["n"] == 2
    assert len(candidates) == 1


def test_retry_on_5xx_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json=_search_response(_video(111)))

    provider = _provider(handler)
    candidates = run(provider.search(_request()))
    assert calls["n"] == 2
    assert len(candidates) == 1


def test_401_raises_auth_error_no_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    provider = _provider(handler)
    with pytest.raises(ProviderAuthError):
        run(provider.search(_request()))
    assert calls["n"] == 1


def test_retries_exhausted_raises_server_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={})

    provider = _provider(handler)
    with pytest.raises(ProviderServerError):
        run(provider.search(_request()))
    assert calls["n"] == 3


def test_rate_limit_exhausted_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    provider = _provider(handler)
    with pytest.raises(ProviderRateLimitError):
        run(provider.search(_request()))


def test_corrupt_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not json")

    provider = _provider(handler)
    with pytest.raises(ProviderResponseError):
        run(provider.search(_request()))


def test_unexpected_status_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={})

    provider = _provider(handler)
    with pytest.raises(ProviderResponseError):
        run(provider.search(_request()))


def test_key_missing_from_config_raises(config: AppConfig) -> None:
    with pytest.raises(ProviderConfigError, match="pexels API key not set"):
        PexelsProvider.from_config(config, env={})


def test_key_from_env(config: AppConfig) -> None:
    config.providers["pexels"] = config.providers["pexels"].model_copy(update={"enabled": True})
    provider = PexelsProvider.from_config(config, env={"PEXELS_API_KEY": "abc"})
    assert provider.api_key == "abc"


def test_disabled_provider_raises(config: AppConfig) -> None:
    config.providers["pexels"] = config.providers["pexels"].model_copy(update={"enabled": False})
    with pytest.raises(ProviderConfigError, match="disabled"):
        PexelsProvider.from_config(config, env={"PEXELS_API_KEY": "abc"})


def test_no_network_all_mocked() -> None:
    """All requests must go through the injected MockTransport, never real net."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.pexels.com"
        return httpx.Response(200, json=_search_response(_video(1)))

    provider = _provider(handler)
    run(provider.search(_request()))
