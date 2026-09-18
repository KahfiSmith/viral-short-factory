"""Wikimedia Commons provider unit tests."""

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
from viral_shorts_factory.providers.wikimedia_commons import WikimediaCommonsProvider


def test_wikimedia_commons_provider_from_config(config: AppConfig) -> None:
    provider = WikimediaCommonsProvider.from_config(config)
    assert provider.name == "wikimedia_commons"
    assert provider.per_page == 20
    assert "ViralShortsFactory" in provider.user_agent


def test_wikimedia_commons_search_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "commons.wikimedia.org/w/api.php" in str(request.url)
        assert request.headers.get("User-Agent") == "TestAgent/1.0"
        return httpx.Response(
            200,
            json={
                "batchcomplete": "",
                "query": {
                    "pages": {
                        "1001": {
                            "pageid": 1001,
                            "ns": 6,
                            "title": "File:Platypus Swimming Australia.jpg",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/wikipedia/commons/1/1a/platypus.jpg",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Platypus_Swimming_Australia.jpg",
                                    "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/platypus.jpg/720px-platypus.jpg",
                                    "width": 1080,
                                    "height": 1920,
                                    "size": 123456,
                                    "mime": "image/jpeg",
                                    "extmetadata": {
                                        "Artist": {
                                            "value": (
                                                '<a href="https://example.com">John Naturalist</a>'
                                            )
                                        },
                                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                        "Categories": {"value": "Monotremes|Fauna of Australia"},
                                    },
                                }
                            ],
                        },
                        "1002": {
                            "pageid": 1002,
                            "ns": 6,
                            "title": "File:Axolotl Movement underwater.webm",
                            "imageinfo": [
                                {
                                    "url": "https://upload.wikimedia.org/wikipedia/commons/2/2b/axolotl.webm",
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Axolotl_Movement_underwater.webm",
                                    "width": 1920,
                                    "height": 1080,
                                    "size": 543210,
                                    "mime": "video/webm",
                                    "extmetadata": {
                                        "Artist": {"value": "Science Lab US"},
                                        "LicenseShortName": {"value": "Public domain"},
                                        "Categories": {"value": "Ambystoma mexicanum"},
                                    },
                                }
                            ],
                        },
                    }
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = WikimediaCommonsProvider(user_agent="TestAgent/1.0", client=client)

    req = AssetSearchRequest(
        scene_id="scene_001",
        query="platypus",
        media_type=MediaType.IMAGE,
        orientation="portrait",
    )

    candidates = asyncio.run(provider.search(req))
    assert len(candidates) == 2

    # Verify first candidate (image, CC BY-SA 4.0)
    img_cand = next(c for c in candidates if c.provider_asset_id == "1001")
    assert img_cand.candidate_id == "wikimedia_commons:1001"
    assert img_cand.provider == "wikimedia_commons"
    assert img_cand.media_type == MediaType.IMAGE
    assert img_cand.rights_status == RightsStatus.ATTRIBUTION_REQUIRED
    assert img_cand.contributor_name == "John Naturalist"
    expected_url = "https://upload.wikimedia.org/wikipedia/commons/1/1a/platypus.jpg"
    assert img_cand.download_variants[0].url == expected_url
    assert img_cand.download_variants[0].width == 1080
    assert img_cand.download_variants[0].height == 1920
    assert "platypus" in img_cand.tags
    assert "monotremes" in img_cand.tags

    # Verify second candidate (video, Public domain)
    vid_cand = next(c for c in candidates if c.provider_asset_id == "1002")
    assert vid_cand.candidate_id == "wikimedia_commons:1002"
    assert vid_cand.media_type == MediaType.VIDEO
    assert vid_cand.rights_status == RightsStatus.PUBLIC_DOMAIN
    assert vid_cand.contributor_name == "Science Lab US"
    assert vid_cand.download_variants[0].file_type == "webm"


def test_wikimedia_commons_search_empty_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"batchcomplete": "", "query": {"pages": {}}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = WikimediaCommonsProvider(client=client)

    req = AssetSearchRequest(scene_id="scene_001", query="nonexistent_xyz_123")
    candidates = asyncio.run(provider.search(req))
    assert candidates == []


def test_wikimedia_commons_rate_limit_retry_exhausted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = WikimediaCommonsProvider(client=client, max_attempts=2)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderRateLimitError, match="Wikimedia Commons rate limit hit"):
        asyncio.run(provider.search(req))


def test_wikimedia_commons_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = WikimediaCommonsProvider(client=client, max_attempts=2)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderServerError, match="Wikimedia Commons server error"):
        asyncio.run(provider.search(req))


def test_wikimedia_commons_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<not valid json>")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = WikimediaCommonsProvider(client=client, max_attempts=1)

    req = AssetSearchRequest(scene_id="scene_001", query="test")
    with pytest.raises(ProviderResponseError, match="invalid JSON"):
        asyncio.run(provider.search(req))
