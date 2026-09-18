"""Wikimedia Commons media provider (official MediaWiki API).

Adapter responsibilities:
- Query https://commons.wikimedia.org/w/api.php with search generator for File: namespace;
- Extract image and video media, dimensions, URLs, MIME types, and licensing metadata;
- Handle rate limits (429) and server errors (5xx) with bounded exponential backoff;
- Parse responses into normalized AssetCandidate objects with appropriate RightsStatus.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import TYPE_CHECKING
from urllib.parse import quote

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
from viral_shorts_factory.providers.pexels import (
    DEFAULT_TIMEOUT,
    MAX_BACKOFF_SECONDS,
)

if TYPE_CHECKING:
    from viral_shorts_factory.providers.base import FootageProvider  # noqa: F401

_log = logging.getLogger("vsf.providers.wikimedia_commons")

WIKIMEDIA_COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
DEFAULT_USER_AGENT = (
    "ViralShortsFactory/1.0 (https://github.com/KahfiSmith/viral-short-factory; "
    "kahfismith@users.noreply.github.com)"
)


def _clean_artist(raw: str) -> str:
    """Strip HTML tags and excess whitespace from artist metadata."""
    if not raw:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", raw).strip()
    return " ".join(cleaned.split())


def _determine_rights_status(license_name: str) -> RightsStatus:
    """Classify Wikimedia Commons license into domain RightsStatus."""
    lower = license_name.lower()
    if any(term in lower for term in ("public domain", "cc0", "pd-", "pd ", "no restrictions")):
        return RightsStatus.PUBLIC_DOMAIN
    if any(term in lower for term in ("cc-by", "cc by", "attribution", "cc-sa", "cc sa")):
        return RightsStatus.ATTRIBUTION_REQUIRED
    if lower:
        return RightsStatus.PROVIDER_LICENSED
    return RightsStatus.UNVERIFIED


def _extract_tags(title: str, categories_str: str) -> list[str]:
    """Generate search tags from file title and categories."""
    tags: list[str] = []
    base_title = re.sub(r"^file:\s*", "", title, flags=re.IGNORECASE)
    base_title = re.sub(r"\.[a-zA-Z0-9]{2,5}$", "", base_title)
    tags.extend(re.findall(r"[a-z0-9]+", base_title.lower()))

    if categories_str:
        for cat in categories_str.split("|"):
            cat_clean = cat.strip().lower()
            if cat_clean and len(cat_clean) > 2:
                tags.append(cat_clean)

    seen: set[str] = set()
    result: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


class WikimediaCommonsProvider:
    """Wikimedia Commons photo and media search adapter."""

    name = "wikimedia_commons"

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
    def from_config(cls, config: AppConfig) -> WikimediaCommonsProvider:
        provider_cfg = config.get_provider("wikimedia_commons")
        user_agent = (
            provider_cfg.user_agent
            if provider_cfg and provider_cfg.user_agent
            else DEFAULT_USER_AGENT
        )
        per_page = provider_cfg.per_page if provider_cfg else 20
        return cls(user_agent=user_agent, per_page=per_page)

    async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
        """Search Wikimedia Commons and map to normalized AssetCandidate objects."""
        limit = min(request.max_results or self.per_page, 50)
        params: dict[str, str | int] = {
            "action": "query",
            "generator": "search",
            "gsrsearch": request.query,
            "gsrnamespace": 6,  # File namespace
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "format": "json",
        }
        headers = {"User-Agent": self.user_agent}

        data = await self._fetch_with_retry(
            WIKIMEDIA_COMMONS_API_URL, params=params, headers=headers
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
                            f"Wikimedia Commons transport error after {attempt} attempts: {exc}"
                        ) from exc
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code == 429:
                    last_error = ProviderRateLimitError(
                        f"Wikimedia Commons rate limit hit (HTTP 429): {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code >= 500:
                    last_error = ProviderServerError(
                        f"Wikimedia Commons server error HTTP {resp.status_code}: {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code != 200:
                    raise ProviderResponseError(
                        f"Wikimedia Commons unexpected HTTP {resp.status_code}: {resp.text}"
                    )

                try:
                    return resp.json()  # type: ignore[no-any-return]
                except Exception as exc:
                    raise ProviderResponseError(
                        f"Wikimedia Commons returned invalid JSON: {exc}"
                    ) from exc

            if last_error:
                raise last_error
            raise ProviderError("Wikimedia Commons retry loop exhausted without result")
        finally:
            if own_client:
                await client.aclose()

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = min(MAX_BACKOFF_SECONDS, (2 ** (attempt - 1)) + random.uniform(0.1, 0.5))  # noqa: S311
        await asyncio.sleep(delay)

    def _normalize(
        self, data: dict[str, object], request: AssetSearchRequest
    ) -> list[AssetCandidate]:
        query_dict = data.get("query")
        if not isinstance(query_dict, dict):
            return []

        pages_dict = query_dict.get("pages")
        if not isinstance(pages_dict, dict):
            return []

        candidates: list[AssetCandidate] = []
        for page_id, page in pages_dict.items():
            if not isinstance(page, dict):
                continue

            imageinfo_list = page.get("imageinfo")
            if not isinstance(imageinfo_list, list) or not imageinfo_list:
                continue

            info = imageinfo_list[0]
            if not isinstance(info, dict):
                continue

            download_url = info.get("url")
            if not download_url or not isinstance(download_url, str):
                continue

            width = int(info.get("width") or 0)
            height = int(info.get("height") or 0)
            mime = str(info.get("mime") or "").lower()

            # Determine media type
            is_video = mime.startswith("video/")
            media_type = MediaType.VIDEO if is_video else MediaType.IMAGE

            # Extract licensing and artist metadata
            ext = info.get("extmetadata")
            ext_dict = ext if isinstance(ext, dict) else {}

            license_name = ""
            if "LicenseShortName" in ext_dict and isinstance(ext_dict["LicenseShortName"], dict):
                license_name = str(ext_dict["LicenseShortName"].get("value") or "")

            raw_artist = ""
            if "Artist" in ext_dict and isinstance(ext_dict["Artist"], dict):
                raw_artist = str(ext_dict["Artist"].get("value") or "")
            artist = _clean_artist(raw_artist)

            categories = ""
            if "Categories" in ext_dict and isinstance(ext_dict["Categories"], dict):
                categories = str(ext_dict["Categories"].get("value") or "")

            title = str(page.get("title") or f"File_{page_id}")
            tags = _extract_tags(title, categories)
            rights_status = _determine_rights_status(license_name)

            source_page_url = info.get("descriptionurl")
            if not source_page_url or not isinstance(source_page_url, str):
                source_page_url = f"https://commons.wikimedia.org/wiki/{quote(title)}"

            file_type = mime.split("/")[-1] if "/" in mime else "jpeg"
            variant = DownloadVariant(
                url=download_url,
                width=width,
                height=height,
                file_type=file_type,
            )

            cand = AssetCandidate(
                candidate_id=f"wikimedia_commons:{page_id}",
                provider="wikimedia_commons",
                provider_asset_id=str(page_id),
                media_type=media_type,
                source_page_url=source_page_url,
                preview_url=(
                    info.get("thumburl")
                    if isinstance(info.get("thumburl"), str)
                    else download_url
                ),
                download_variants=[variant],
                width=width,
                height=height,
                tags=tags,
                query=request.query,
                rights_status=rights_status,
                contributor_name=artist or None,
            )
            candidates.append(cand)

        return candidates
