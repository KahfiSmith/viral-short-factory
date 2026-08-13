"""Tests for YouTube trend signals provider (Milestone 13)."""

from __future__ import annotations

import httpx
import pytest

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.providers.youtube_trends import (
    TrendSignalError,
    YouTubeTrendProvider,
)


def test_youtube_trends_missing_key(config: AppConfig, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    provider = YouTubeTrendProvider(config)
    with pytest.raises(TrendSignalError, match="YOUTUBE_API_KEY"):
        provider.fetch_popular_sports_signals()


def test_youtube_trends_mocked_success(config: AppConfig, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy_key")

    mock_response = {
        "items": [
            {
                "id": "vid_123",
                "snippet": {
                    "title": "Neuer Tarkam Skills",
                    "channelTitle": "Football Channel",
                    "publishedAt": "2026-08-10T00:00:00Z",
                },
                "statistics": {
                    "viewCount": "10000",
                    "likeCount": "500",
                },
            }
        ]
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert "chart=mostPopular" in str(request.url)
        assert "regionCode=ID" in str(request.url)
        assert "videoCategoryId=17" in str(request.url)
        return httpx.Response(200, json=mock_response)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    provider = YouTubeTrendProvider(config, client=client)

    signals = provider.fetch_popular_sports_signals()
    assert len(signals.videos) == 1
    assert signals.videos[0].video_id == "vid_123"
    assert signals.videos[0].title == "Neuer Tarkam Skills"
    assert signals.videos[0].view_count == 10000
