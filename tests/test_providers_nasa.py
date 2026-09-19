"""NASA media provider unit tests."""

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
from viral_shorts_factory.providers.nasa import NasaProvider


def test_nasa_provider_from_config(config: AppConfig) -> None:
    provider = NasaProvider.from_config(config)
    assert provider.name == "nasa"
    assert provider.per_page == 20
    assert "ViralShortsFactory" in provider.user_agent


def test_nasa_search_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "images-api.nasa.gov/search" in url_str:
            return httpx.Response(
                200,
                json={
                    "collection": {
                        "items": [
                            {
                                "href": "https://images-assets.nasa.gov/video/vid_101/collection.json",
                                "data": [
                                    {
                                        "nasa_id": "vid_101",
                                        "title": "Black Hole Collision Simulation",
                                        "media_type": "video",
                                        "center": "GSFC",
                                        "keywords": ["Black Hole, astrophysics, simulation"],
                                    }
                                ],
                                "links": [
                                    {
                                        "href": "https://images-assets.nasa.gov/video/vid_101/vid_101~thumb.jpg"
                                    }
                                ],
                            },
                            {
                                "href": "https://images-assets.nasa.gov/image/img_202/collection.json",
                                "data": [
                                    {
                                        "nasa_id": "img_202",
                                        "title": "Deep Field Galaxy Cluster",
                                        "media_type": "image",
                                        "center": "JPL",
                                        "keywords": ["JWST, galaxy, cosmology"],
                                    }
                                ],
                                "links": [
                                    {
                                        "href": "https://images-assets.nasa.gov/image/img_202/img_202~thumb.jpg"
                                    }
                                ],
                            },
                        ]
                    }
                },
            )
        if "vid_101/collection.json" in url_str:
            return httpx.Response(
                200,
                json=[
                    "http://images-assets.nasa.gov/video/vid_101/vid_101~orig.mp4",
                    "http://images-assets.nasa.gov/video/vid_101/vid_101~large.mp4",
                    "http://images-assets.nasa.gov/video/vid_101/vid_101~medium.mp4",
                ],
            )
        if "img_202/collection.json" in url_str:
            return httpx.Response(
                200,
                json=[
                    "http://images-assets.nasa.gov/image/img_202/img_202~orig.jpg",
                    "http://images-assets.nasa.gov/image/img_202/img_202~large.jpg",
                    "http://images-assets.nasa.gov/image/img_202/img_202~medium.jpg",
                ],
            )
        return httpx.Response(404, text="Not Found")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = NasaProvider(client=client)

    req = AssetSearchRequest(scene_id="scene_001", query="black hole", media_type=MediaType.VIDEO)
    candidates = asyncio.run(provider.search(req))
    assert len(candidates) == 2

    # Check video candidate
    vid = next(c for c in candidates if c.provider_asset_id == "vid_101")
    assert vid.candidate_id == "nasa:vid_101"
    assert vid.media_type == MediaType.VIDEO
    assert vid.rights_status == RightsStatus.PUBLIC_DOMAIN
    assert vid.contributor_name == "GSFC"
    assert vid.download_variants[0].url.startswith("https://")
    assert vid.download_variants[0].file_type == "mp4"
    assert "black" in vid.tags
    assert "astrophysics" in vid.tags

    # Check image candidate
    img = next(c for c in candidates if c.provider_asset_id == "img_202")
    assert img.candidate_id == "nasa:img_202"
    assert img.media_type == MediaType.IMAGE
    assert img.rights_status == RightsStatus.PUBLIC_DOMAIN
    assert img.contributor_name == "JPL"
    assert img.download_variants[0].url.startswith("https://")
    assert img.download_variants[0].file_type == "jpg"
    assert "jwst" in img.tags


def test_nasa_search_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"collection": {"items": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = NasaProvider(client=client)

    req = AssetSearchRequest(scene_id="scene_001", query="empty_test")
    candidates = asyncio.run(provider.search(req))
    assert candidates == []


def test_nasa_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = NasaProvider(client=client, max_attempts=2)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderRateLimitError, match="NASA API rate limit hit"):
        asyncio.run(provider.search(req))


def test_nasa_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = NasaProvider(client=client, max_attempts=2)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderServerError, match="NASA API server error"):
        asyncio.run(provider.search(req))


def test_nasa_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = NasaProvider(client=client, max_attempts=1)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderResponseError, match="invalid JSON"):
        asyncio.run(provider.search(req))
