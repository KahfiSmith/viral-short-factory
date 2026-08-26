"""Unsplash provider unit and integration tests."""

from __future__ import annotations

import httpx
import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetSearchRequest, MediaType, RightsStatus
from viral_shorts_factory.providers.base import ProviderAuthError
from viral_shorts_factory.providers.pexels import ProviderConfigError
from viral_shorts_factory.providers.unsplash import UnsplashProvider


def test_unsplash_provider_missing_key(config: AppConfig) -> None:
    with pytest.raises(ProviderConfigError, match="missing Unsplash access key"):
        UnsplashProvider.from_config(config, env={})


def test_unsplash_provider_from_config(config: AppConfig) -> None:
    provider = UnsplashProvider.from_config(config, env={"UNSPLASH_ACCESS_KEY": "dummy_key"})
    assert provider.name == "unsplash"
    assert provider.access_key == "dummy_key"


def test_unsplash_search_success() -> None:
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.unsplash.com/search/photos" in str(request.url)
        assert request.headers.get("Authorization") == "Client-ID test_key"
        return httpx.Response(
            200,
            json={
                "total": 1,
                "results": [
                    {
                        "id": "photo_123",
                        "width": 1080,
                        "height": 1920,
                        "description": "A beautiful betta fish",
                        "alt_description": "betta swimming",
                        "urls": {
                            "full": "https://images.unsplash.com/photo-123-full.jpg",
                            "small": "https://images.unsplash.com/photo-123-small.jpg",
                        },
                        "links": {
                            "html": "https://unsplash.com/photos/photo_123",
                        },
                        "user": {
                            "name": "Jane Doe",
                            "username": "janedoe",
                        },
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = UnsplashProvider(access_key="test_key", client=client)

    req = AssetSearchRequest(
        scene_id="scene_001",
        query="betta fish",
        media_type=MediaType.IMAGE,
        orientation="portrait",
    )

    candidates = asyncio.run(provider.search(req))
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.candidate_id == "unsplash:photo_123"
    assert cand.provider == "unsplash"
    assert cand.media_type == MediaType.IMAGE
    assert cand.rights_status == RightsStatus.PROVIDER_LICENSED
    assert cand.download_variants[0].url == "https://images.unsplash.com/photo-123-full.jpg"
    assert cand.contributor_name == "Jane Doe"


def test_unsplash_auth_error() -> None:
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = UnsplashProvider(access_key="bad_key", client=client)

    req = AssetSearchRequest(
        scene_id="scene_001",
        query="test",
        media_type=MediaType.IMAGE,
    )
    with pytest.raises(ProviderAuthError, match="Unsplash auth rejected"):
        asyncio.run(provider.search(req))
