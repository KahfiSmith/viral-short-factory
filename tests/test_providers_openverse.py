"""Openverse provider unit tests."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetSearchRequest, MediaType, RightsStatus
from viral_shorts_factory.providers.base import (
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)
from viral_shorts_factory.providers.openverse import OpenverseProvider


def test_openverse_provider_from_config(config: AppConfig) -> None:
    provider = OpenverseProvider.from_config(config)
    assert provider.name == "openverse"
    assert provider.per_page == 20
    assert "ViralShortsFactory" in provider.user_agent


def test_openverse_search_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.openverse.org/v1/images/" in str(request.url)
        assert request.headers.get("User-Agent") == "TestAgent/1.0"
        return httpx.Response(
            200,
            json={
                "result_count": 2,
                "results": [
                    {
                        "id": "img_001",
                        "title": "Duck-billed Platypus in Creek",
                        "creator": "Smithsonian Institution",
                        "url": "https://live.staticflickr.com/123/platypus_01.jpg",
                        "thumbnail": "https://api.openverse.org/thumb_01.jpg",
                        "foreign_landing_url": "https://www.si.edu/object/platypus_01",
                        "license": "cc0",
                        "width": 1920,
                        "height": 1080,
                        "filetype": "jpg",
                        "tags": [{"name": "platypus"}, {"name": "monotreme"}],
                    },
                    {
                        "id": "img_002",
                        "title": "Mexican Axolotl Aquarium",
                        "creator": "Aquatic Bio Lab",
                        "url": "https://images.museum.org/axolotl_02.png",
                        "foreign_landing_url": "https://museum.org/axolotl_02",
                        "license": "by",
                        "width": 1080,
                        "height": 1920,
                        "filetype": "png",
                        "tags": [{"name": "axolotl"}, {"name": "amphibian"}],
                    },
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenverseProvider(user_agent="TestAgent/1.0", client=client)

    req = AssetSearchRequest(scene_id="scene_001", query="platypus", media_type=MediaType.IMAGE)
    candidates = asyncio.run(provider.search(req))
    assert len(candidates) == 2

    # Verify first candidate (CC0 -> PUBLIC_DOMAIN)
    c1 = next(c for c in candidates if c.provider_asset_id == "img_001")
    assert c1.candidate_id == "openverse:img_001"
    assert c1.provider == "openverse"
    assert c1.media_type == MediaType.IMAGE
    assert c1.rights_status == RightsStatus.PUBLIC_DOMAIN
    assert c1.contributor_name == "Smithsonian Institution"
    assert c1.download_variants[0].url == "https://live.staticflickr.com/123/platypus_01.jpg"
    assert c1.download_variants[0].width == 1920
    assert c1.download_variants[0].height == 1080
    assert "platypus" in c1.tags
    assert "monotreme" in c1.tags

    # Verify second candidate (BY -> ATTRIBUTION_REQUIRED)
    c2 = next(c for c in candidates if c.provider_asset_id == "img_002")
    assert c2.candidate_id == "openverse:img_002"
    assert c2.media_type == MediaType.IMAGE
    assert c2.rights_status == RightsStatus.ATTRIBUTION_REQUIRED
    assert c2.contributor_name == "Aquatic Bio Lab"
    assert c2.download_variants[0].file_type == "png"


def test_openverse_search_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenverseProvider(client=client)

    req = AssetSearchRequest(scene_id="scene_001", query="empty_test")
    candidates = asyncio.run(provider.search(req))
    assert candidates == []


def test_openverse_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenverseProvider(client=client, max_attempts=2)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderRateLimitError, match="Openverse rate limit hit"):
        asyncio.run(provider.search(req))


def test_openverse_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenverseProvider(client=client, max_attempts=2)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderServerError, match="Openverse server error"):
        asyncio.run(provider.search(req))


def test_openverse_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenverseProvider(client=client, max_attempts=1)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderResponseError, match="invalid JSON"):
        asyncio.run(provider.search(req))
