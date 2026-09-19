"""Openverse media provider (official Openverse API).

Adapter responsibilities:
- Query https://api.openverse.org/v1/images/ with commercial-safe license filters;
- Extract high-resolution image URLs, dimensions, creator, and Creative Commons license;
- Handle rate limits (429) and server errors (5xx) with bounded exponential backoff;
- Map responses to normalized AssetCandidate objects with appropriate RightsStatus.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import TYPE_CHECKING

import httpx

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import (
    AssetCandidate,
    AssetSearchRequest,
    DownloadVariant,
    MediaType,
    RightsStatus,
)
from viral_shorts_factory.providers.base import (
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)
from viral_shorts_factory.providers.pexels import DEFAULT_TIMEOUT, MAX_BACKOFF_SECONDS

if TYPE_CHECKING:
    from viral_shorts_factory.providers.base import FootageProvider  # noqa: F401

_log = logging.getLogger("vsf.providers.openverse")

OPENVERSE_IMAGES_API_URL = "https://api.openverse.org/v1/images/"
DEFAULT_USER_AGENT = (
    "ViralShortsFactory/1.0 (https://github.com/KahfiSmith/viral-short-factory; "
    "kahfismith@users.noreply.github.com)"
)


def _determine_rights_status(license_code: str) -> RightsStatus:
    """Classify Openverse license into domain RightsStatus."""
    code = (license_code or "").lower()
    if code in ("cc0", "pdm", "publicdomain"):
        return RightsStatus.PUBLIC_DOMAIN
    if code:
        return RightsStatus.ATTRIBUTION_REQUIRED
    return RightsStatus.UNVERIFIED


def _extract_tags(title: str, tag_list: list[dict[str, object]]) -> list[str]:
    """Extract search tags from title and Openverse tag dicts."""
    tags: list[str] = []
    tags.extend(re.findall(r"[a-z0-9]+", (title or "").lower()))
    for t in tag_list:
        if isinstance(t, dict):
            name = str(t.get("name") or "").strip().lower()
            if name and len(name) > 2:
                tags.append(name)

    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


class OpenverseProvider:
    """Openverse image search adapter."""

    name = "openverse"

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        client: httpx.AsyncClient | None = None,
        *,
        per_page: int = 20,
        max_attempts: int = 3,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.user_agent = user_agent
        self._client = client
        self.per_page = per_page
        self.max_attempts = max_attempts
        self.timeout = timeout

    @classmethod
    def from_config(cls, config: AppConfig) -> OpenverseProvider:
        provider_cfg = config.get_provider("openverse")
        user_agent = (
            provider_cfg.user_agent
            if provider_cfg and provider_cfg.user_agent
            else DEFAULT_USER_AGENT
        )
        per_page = provider_cfg.per_page if provider_cfg else 20
        return cls(user_agent=user_agent, per_page=per_page)

    async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
        """Search Openverse and map to normalized AssetCandidate items."""
        limit = min(request.max_results or self.per_page, 50)
        params: dict[str, str | int] = {
            "q": request.query,
            "page_size": limit,
            "license_type": "commercial",
        }
        headers = {"User-Agent": self.user_agent}

        data = await self._fetch_with_retry(
            OPENVERSE_IMAGES_API_URL, params=params, headers=headers
        )
        return self._normalize(data, request)

    async def _fetch_with_retry(
        self, url: str, params: dict[str, str | int], headers: dict[str, str]
    ) -> dict[str, object]:
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        attempt = 0
        last_error: Exception | None = None

        try:
            while attempt < self.max_attempts:
                attempt += 1
                try:
                    resp = await client.get(url, params=params, headers=headers)
                except httpx.RequestError as exc:
                    last_error = exc
                    if attempt >= self.max_attempts:
                        raise ProviderServerError(
                            f"Openverse transport error after {attempt} attempts: {exc}"
                        ) from exc
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code == 429:
                    last_error = ProviderRateLimitError(
                        f"Openverse rate limit hit (HTTP 429): {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code >= 500:
                    last_error = ProviderServerError(
                        f"Openverse server error HTTP {resp.status_code}: {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code != 200:
                    raise ProviderResponseError(
                        f"Openverse unexpected HTTP {resp.status_code}: {resp.text}"
                    )

                try:
                    return resp.json()  # type: ignore[no-any-return]
                except Exception as exc:
                    raise ProviderResponseError(
                        f"Openverse returned invalid JSON: {exc}"
                    ) from exc

            if last_error:
                raise last_error
            raise ProviderError("Openverse retry loop exhausted without result")
        finally:
            if own_client:
                await client.aclose()

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = min(MAX_BACKOFF_SECONDS, (2 ** (attempt - 1)) + random.uniform(0.1, 0.5))  # noqa: S311
        await asyncio.sleep(delay)

    def _normalize(
        self, data: dict[str, object], request: AssetSearchRequest
    ) -> list[AssetCandidate]:
        results = data.get("results")
        if not isinstance(results, list):
            return []

        candidates: list[AssetCandidate] = []
        for item in results:
            if not isinstance(item, dict):
                continue

            img_id = str(item.get("id") or "")
            download_url = item.get("url")
            if not img_id or not download_url or not isinstance(download_url, str):
                continue

            width = int(item.get("width") or 0)
            height = int(item.get("height") or 0)
            file_type = item.get("filetype") or "jpg"
            if isinstance(file_type, str):
                file_type = file_type.lower()
            else:
                file_type = "jpg"

            variant = DownloadVariant(
                url=download_url,
                width=width,
                height=height,
                file_type=file_type,
            )

            title = str(item.get("title") or f"openverse_{img_id}")
            raw_tags = item.get("tags") or []
            tag_list = raw_tags if isinstance(raw_tags, list) else []
            tags = _extract_tags(title, tag_list)

            license_code = str(item.get("license") or "")
            rights_status = _determine_rights_status(license_code)

            creator = item.get("creator")
            contributor_name = str(creator).strip() if creator else None

            source_page_url = (
                str(item.get("foreign_landing_url") or item.get("detail_url") or download_url)
            )
            preview_url = str(item.get("thumbnail") or download_url)

            cand = AssetCandidate(
                candidate_id=f"openverse:{img_id}",
                provider="openverse",
                provider_asset_id=img_id,
                media_type=MediaType.IMAGE,
                source_page_url=source_page_url,
                preview_url=preview_url,
                download_variants=[variant],
                width=width,
                height=height,
                tags=tags,
                query=request.query,
                rights_status=rights_status,
                contributor_name=contributor_name,
            )
            candidates.append(cand)

        return candidates
