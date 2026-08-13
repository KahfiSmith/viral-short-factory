"""YouTube trend signals provider for topic/format inspiration (docs/04 §4, docs/05 M13)."""

from __future__ import annotations

import os

import httpx
from pydantic import BaseModel

from viral_shorts_factory.config.models import AppConfig


class TrendSignalError(Exception):
    """Raised when trend signal fetching fails."""


class YouTubeTrendVideo(BaseModel):
    """Normalized video trend signal record."""

    video_id: str
    title: str
    channel_title: str
    published_at: str
    view_count: int = 0
    like_count: int = 0


class YouTubeTrendResponse(BaseModel):
    """Container for YouTube mostPopular sports trend signals."""

    region_code: str = "ID"
    category_id: str = "17"
    videos: list[YouTubeTrendVideo]


class YouTubeTrendProvider:
    """Fetch YouTube mostPopular sports video trend signals (docs/04 §4)."""

    def __init__(self, config: AppConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        provider_cfg = config.providers.get("youtube_trends")
        env_var = provider_cfg.api_key_env if provider_cfg else "YOUTUBE_API_KEY"
        self.api_key = os.environ.get(env_var or "YOUTUBE_API_KEY", "")
        self._client = client

    def fetch_popular_sports_signals(
        self,
        region_code: str = "ID",
        category_id: str = "17",
        max_results: int = 10,
    ) -> YouTubeTrendResponse:
        """Fetch YouTube mostPopular videos in category (17=Sports)."""
        if not self.api_key:
            raise TrendSignalError("YOUTUBE_API_KEY environment variable not set")

        url = "https://www.googleapis.com/youtube/v3/videos"
        params: dict[str, str | int] = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region_code,
            "videoCategoryId": category_id,
            "maxResults": max_results,
            "key": self.api_key,
        }

        client = self._client or httpx.Client(timeout=10.0)
        close_client = self._client is None

        try:
            res = client.get(url, params=params)
            if res.status_code != 200:
                raise TrendSignalError(f"YouTube API returned status {res.status_code}: {res.text}")
            data = res.json()
        except Exception as exc:
            if not isinstance(exc, TrendSignalError):
                raise TrendSignalError(f"HTTP request failed: {exc}") from exc
            raise
        finally:
            if close_client:
                client.close()

        videos: list[YouTubeTrendVideo] = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            videos.append(
                YouTubeTrendVideo(
                    video_id=item.get("id", ""),
                    title=snippet.get("title", ""),
                    channel_title=snippet.get("channelTitle", ""),
                    published_at=snippet.get("publishedAt", ""),
                    view_count=int(stats.get("viewCount", 0)),
                    like_count=int(stats.get("likeCount", 0)),
                )
            )

        return YouTubeTrendResponse(
            region_code=region_code,
            category_id=category_id,
            videos=videos,
        )
