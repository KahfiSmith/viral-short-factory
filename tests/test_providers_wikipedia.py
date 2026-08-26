"""Wikipedia provider unit and integration tests."""

from __future__ import annotations

import httpx
import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.providers.wikipedia import (
    WikipediaProvider,
    WikipediaSignalError,
    WikipediaSignals,
)


def test_wikipedia_provider_init_from_config(config: AppConfig) -> None:
    provider = WikipediaProvider.from_config(config)
    assert provider.name == "wikipedia"
    assert provider.language == "id"


def test_wikipedia_fetch_summary_direct_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "id.wikipedia.org/api/rest_v1/page/summary/Komodo" in str(request.url)
        assert "User-Agent" in request.headers
        return httpx.Response(
            200,
            json={
                "title": "Komodo",
                "extract": "Komodo adalah spesies biawak besar yang terdapat di Pulau Komodo.",
                "description": "Spesies kadal terbesar di dunia",
                "content_urls": {"desktop": {"page": "https://id.wikipedia.org/wiki/Komodo"}},
                "thumbnail": {"source": "https://upload.wikimedia.org/komodo.jpg"},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = WikipediaProvider(language="id", client=client)

    signals: WikipediaSignals = provider.fetch_summary("Komodo")
    assert signals.query == "Komodo"
    assert signals.language == "id"
    assert signals.summary is not None
    assert signals.summary.title == "Komodo"
    assert "spesies biawak besar" in signals.summary.extract
    assert signals.summary.page_url == "https://id.wikipedia.org/wiki/Komodo"
    assert signals.summary.thumbnail_url == "https://upload.wikimedia.org/komodo.jpg"
    assert len(signals.related_extracts) == 1


def test_wikipedia_fetch_summary_fallback_opensearch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "api/rest_v1/page/summary/ikan_cupang_liar" in url_str:
            return httpx.Response(404, json={"type": "https://mediawiki.org/wiki/HyperSwitch/errors/not_found"})
        if "action=opensearch" in url_str:
            return httpx.Response(
                200,
                json=[
                    "ikan cupang liar",
                    ["Cupang"],
                    ["Ikan air tawar"],
                    ["https://id.wikipedia.org/wiki/Cupang"],
                ],
            )
        if "api/rest_v1/page/summary/Cupang" in url_str:
            return httpx.Response(
                200,
                json={
                    "title": "Cupang",
                    "extract": (
                        "Cupang adalah ikan air tawar yang habitat asalnya "
                        "adalah beberapa negara di Asia Tenggara."
                    ),
                    "description": "Genus ikan air tawar",
                    "content_urls": {"desktop": {"page": "https://id.wikipedia.org/wiki/Cupang"}},
                },
            )
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = WikipediaProvider(language="id", client=client)

    signals = provider.fetch_summary("ikan cupang liar")
    assert signals.summary is not None
    assert signals.summary.title == "Cupang"
    assert "ikan air tawar" in signals.summary.extract


def test_wikipedia_fetch_error_surfaces() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = WikipediaProvider(language="id", client=client)

    with pytest.raises(WikipediaSignalError, match="HTTP 500"):
        provider.fetch_summary("Error Topic")
