"""Wikipedia content and summary signals provider for topic inspiration and facts."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from viral_shorts_factory.config.models import AppConfig

_log = logging.getLogger("vsf.providers.wikipedia")

DEFAULT_USER_AGENT = (
    "ViralShortsFactory/1.0 (https://github.com/viral-shorts-factory; contact@example.com)"
)


class WikipediaSignalError(Exception):
    """Raised when Wikipedia signal fetching fails."""


class WikipediaPageSummary(BaseModel):
    """Summary information for a Wikipedia page."""

    title: str
    extract: str
    description: str | None = None
    page_url: str | None = None
    thumbnail_url: str | None = None
    language: str = "id"


class WikipediaSignals(BaseModel):
    """Container for topic research signals from Wikipedia."""

    query: str
    language: str = "id"
    summary: WikipediaPageSummary | None = None
    related_extracts: list[str] = Field(default_factory=list)


class WikipediaProvider:
    """Provider for Wikipedia REST API topic research and facts."""

    name = "wikipedia"

    def __init__(
        self,
        language: str = "id",
        user_agent: str = DEFAULT_USER_AGENT,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.language = language
        self.user_agent = user_agent
        self._client = client
        self.timeout = timeout

    @classmethod
    def from_config(cls, config: AppConfig) -> WikipediaProvider:
        provider_cfg = config.providers.get("wikipedia")
        language = provider_cfg.language if provider_cfg and provider_cfg.language else "id"
        user_agent = (
            provider_cfg.user_agent
            if provider_cfg and provider_cfg.user_agent
            else DEFAULT_USER_AGENT
        )
        return cls(language=language, user_agent=user_agent)

    def fetch_summary(self, topic: str, language: str | None = None) -> WikipediaSignals:
        """Fetch REST summary for a given topic."""
        lang = language or self.language
        encoded_topic = quote(topic.replace(" ", "_"))
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_topic}"
        headers = {"User-Agent": self.user_agent}

        client = self._client or httpx.Client(timeout=self.timeout)
        close_client = self._client is None

        try:
            res = client.get(url, headers=headers)
            if res.status_code == 404:
                # If exact title not found, search via opensearch
                return self._search_and_fetch_fallback(topic, lang, client)
            if res.status_code != 200:
                raise WikipediaSignalError(
                    f"Wikipedia REST API returned HTTP {res.status_code}: {res.text}"
                )
            data: dict[str, Any] = res.json()
        except Exception as exc:
            if not isinstance(exc, WikipediaSignalError):
                raise WikipediaSignalError(f"Wikipedia request failed: {exc}") from exc
            raise
        finally:
            if close_client:
                client.close()

        summary = WikipediaPageSummary(
            title=data.get("title", topic),
            extract=data.get("extract", ""),
            description=data.get("description"),
            page_url=data.get("content_urls", {}).get("desktop", {}).get("page"),
            thumbnail_url=data.get("thumbnail", {}).get("source"),
            language=lang,
        )

        return WikipediaSignals(
            query=topic,
            language=lang,
            summary=summary,
            related_extracts=[summary.extract] if summary.extract else [],
        )

    def _search_and_fetch_fallback(
        self, topic: str, lang: str, client: httpx.Client
    ) -> WikipediaSignals:
        """Fallback to opensearch to find closest page title when direct summary is 404."""
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": topic,
            "limit": "1",
            "namespace": "0",
            "format": "json",
        }
        headers = {"User-Agent": self.user_agent}
        res = client.get(search_url, params=params, headers=headers)
        if res.status_code != 200:
            return WikipediaSignals(query=topic, language=lang, summary=None)

        data = res.json()
        # opensearch returns [query, [titles], [descriptions], [urls]]
        if isinstance(data, list) and len(data) >= 2 and data[1]:
            best_title = data[1][0]
            encoded_title = quote(best_title.replace(" ", "_"))
            summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
            sum_res = client.get(summary_url, headers=headers)
            if sum_res.status_code == 200:
                s_data = sum_res.json()
                summary = WikipediaPageSummary(
                    title=s_data.get("title", best_title),
                    extract=s_data.get("extract", ""),
                    description=s_data.get("description"),
                    page_url=s_data.get("content_urls", {}).get("desktop", {}).get("page"),
                    thumbnail_url=s_data.get("thumbnail", {}).get("source"),
                    language=lang,
                )
                return WikipediaSignals(
                    query=topic,
                    language=lang,
                    summary=summary,
                    related_extracts=[summary.extract] if summary.extract else [],
                )

        return WikipediaSignals(query=topic, language=lang, summary=None)
