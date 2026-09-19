"""NASA Images and Video Library provider (official NASA API).

Adapter responsibilities:
- Query https://images-api.nasa.gov/search for videos and images;
- Resolve asset manifests (collection.json) to locate direct MP4 and JPG URLs;
- Normalize http:// URLs to https:// for secure and compliant download;
- Map metadata (NASA ID, center, keywords, license) to normalized AssetCandidate;
- All NASA media is US Government work and marked RightsStatus.PUBLIC_DOMAIN.
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
from viral_shorts_factory.providers.pexels import MAX_BACKOFF_SECONDS

if TYPE_CHECKING:
    from viral_shorts_factory.providers.base import FootageProvider  # noqa: F401

_log = logging.getLogger("vsf.providers.nasa")

NASA_SEARCH_API_URL = "https://images-api.nasa.gov/search"
DEFAULT_TIMEOUT = 20.0
DEFAULT_USER_AGENT = (
    "ViralShortsFactory/1.0 (https://github.com/KahfiSmith/viral-short-factory; "
    "kahfismith@users.noreply.github.com)"
)


def _extract_tags(title: str, keywords: list[str]) -> list[str]:
    """Generate search tags from NASA title and keywords."""
    tags: list[str] = []
    tags.extend(re.findall(r"[a-z0-9]+", title.lower()))
    for kw in keywords:
        for term in kw.split(","):
            cleaned = term.strip().lower()
            if cleaned and len(cleaned) > 2:
                tags.append(cleaned)

    seen: set[str] = set()
    result: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _resolve_variants_from_manifest(
    manifest_urls: list[str], is_video: bool
) -> list[DownloadVariant]:
    """Extract and prioritize download variants from collection.json URLs."""
    variants: list[DownloadVariant] = []
    normalized_urls = [
        u.replace("http://", "https://")
        for u in manifest_urls
        if isinstance(u, str) and u.startswith(("http://", "https://"))
    ]

    if is_video:
        mp4_urls = [u for u in normalized_urls if u.lower().endswith(".mp4")]
        for u in mp4_urls:
            lower = u.lower()
            if "~orig.mp4" in lower:
                variants.append(DownloadVariant(url=u, width=1920, height=1080, file_type="mp4"))
            elif "~large.mp4" in lower:
                variants.append(DownloadVariant(url=u, width=1920, height=1080, file_type="mp4"))
            elif "~medium.mp4" in lower:
                variants.append(DownloadVariant(url=u, width=1280, height=720, file_type="mp4"))
            elif "~small.mp4" in lower or "~mobile.mp4" in lower:
                variants.append(DownloadVariant(url=u, width=640, height=360, file_type="mp4"))
            else:
                variants.append(DownloadVariant(url=u, width=1280, height=720, file_type="mp4"))
    else:
        jpg_urls = [
            u for u in normalized_urls if u.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        for u in jpg_urls:
            lower = u.lower()
            if "~orig.jpg" in lower:
                variants.append(DownloadVariant(url=u, width=1920, height=1080, file_type="jpg"))
            elif "~large.jpg" in lower:
                variants.append(DownloadVariant(url=u, width=1920, height=1080, file_type="jpg"))
            elif "~medium.jpg" in lower:
                variants.append(DownloadVariant(url=u, width=1280, height=720, file_type="jpg"))
            elif "~small.jpg" in lower:
                variants.append(DownloadVariant(url=u, width=640, height=360, file_type="jpg"))
            else:
                variants.append(DownloadVariant(url=u, width=1280, height=720, file_type="jpg"))

    return variants


class NasaProvider:
    """NASA Images and Video Library footage & image provider."""

    name = "nasa"

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
    def from_config(cls, config: AppConfig) -> NasaProvider:
        provider_cfg = config.get_provider("nasa")
        user_agent = (
            provider_cfg.user_agent
            if provider_cfg and provider_cfg.user_agent
            else DEFAULT_USER_AGENT
        )
        per_page = provider_cfg.per_page if provider_cfg else 20
        return cls(user_agent=user_agent, per_page=per_page)

    async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
        """Search NASA API and return normalized AssetCandidate items."""
        limit = min(request.max_results or self.per_page, 50)
        media_type_filter = "video,image"
        if request.media_type == MediaType.VIDEO:
            media_type_filter = "video"
        elif request.media_type == MediaType.IMAGE:
            media_type_filter = "image"

        params: dict[str, str | int] = {
            "q": request.query,
            "media_type": media_type_filter,
            "page_size": limit,
        }
        headers = {"User-Agent": self.user_agent}

        data = await self._fetch_json_with_retry(
            NASA_SEARCH_API_URL, params=params, headers=headers
        )
        if not isinstance(data, dict):
            return []
        collection = data.get("collection")
        if not isinstance(collection, dict):
            return []
        items = collection.get("items", [])
        if not isinstance(items, list) or not items:
            return []

        # Concurrently fetch manifests for returned items
        tasks = []
        for item in items[:limit]:
            manifest_url = item.get("href")
            if manifest_url and isinstance(manifest_url, str):
                tasks.append(self._fetch_manifest(manifest_url, headers))
            else:
                tasks.append(asyncio.sleep(0, result=[]))

        manifest_results = await asyncio.gather(*tasks, return_exceptions=True)

        candidates: list[AssetCandidate] = []
        for item, m_res in zip(items[:limit], manifest_results, strict=False):
            if isinstance(m_res, Exception) or not isinstance(m_res, list) or not m_res:
                continue

            data_list = item.get("data", [])
            if not isinstance(data_list, list) or not data_list:
                continue
            meta = data_list[0]
            if not isinstance(meta, dict):
                continue

            nasa_id = str(meta.get("nasa_id") or "")
            if not nasa_id:
                continue

            raw_media_type = str(meta.get("media_type") or "").lower()
            is_video = raw_media_type == "video"
            cand_media_type = MediaType.VIDEO if is_video else MediaType.IMAGE

            variants = _resolve_variants_from_manifest(m_res, is_video=is_video)
            if not variants:
                continue

            title = str(meta.get("title") or nasa_id)
            center = str(meta.get("center") or "NASA")
            keywords_val = meta.get("keywords") or []
            keywords: list[str] = (
                keywords_val if isinstance(keywords_val, list) else [str(keywords_val)]
            )
            tags = _extract_tags(title, keywords)

            preview_url = None
            links = item.get("links", [])
            if isinstance(links, list) and links:
                for lk in links:
                    if isinstance(lk, dict) and lk.get("href"):
                        preview_url = str(lk["href"]).replace("http://", "https://")
                        break

            if not preview_url and variants:
                preview_url = variants[0].url

            source_page_url = f"https://images.nasa.gov/details/{quote(nasa_id)}"

            cand = AssetCandidate(
                candidate_id=f"nasa:{nasa_id}",
                provider="nasa",
                provider_asset_id=nasa_id,
                media_type=cand_media_type,
                source_page_url=source_page_url,
                preview_url=preview_url,
                download_variants=variants,
                width=variants[0].width,
                height=variants[0].height,
                tags=tags,
                query=request.query,
                rights_status=RightsStatus.PUBLIC_DOMAIN,
                contributor_name=center,
            )
            candidates.append(cand)

        return candidates

    async def _fetch_manifest(self, url: str, headers: dict[str, str]) -> list[str]:
        """Fetch asset collection.json manifest."""
        manifest_data = await self._fetch_json_with_retry(
            url.replace("http://", "https://"), params={}, headers=headers
        )
        if isinstance(manifest_data, list):
            return [str(u) for u in manifest_data if isinstance(u, str)]
        return []

    async def _fetch_json_with_retry(
        self, url: str, params: dict[str, str | int], headers: dict[str, str]
    ) -> dict[str, object] | list[object]:
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
                            f"NASA API transport error after {attempt} attempts: {exc}"
                        ) from exc
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code == 429:
                    last_error = ProviderRateLimitError(
                        f"NASA API rate limit hit (HTTP 429): {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code >= 500:
                    last_error = ProviderServerError(
                        f"NASA API server error HTTP {resp.status_code}: {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code != 200:
                    raise ProviderResponseError(
                        f"NASA API unexpected HTTP {resp.status_code}: {resp.text}"
                    )

                try:
                    return resp.json()  # type: ignore[no-any-return]
                except Exception as exc:
                    raise ProviderResponseError(
                        f"NASA API returned invalid JSON: {exc}"
                    ) from exc

            if last_error:
                raise last_error
            raise ProviderError("NASA API retry loop exhausted without result")
        finally:
            if own_client:
                await client.aclose()

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = min(MAX_BACKOFF_SECONDS, (2 ** (attempt - 1)) + random.uniform(0.1, 0.5))  # noqa: S311
        await asyncio.sleep(delay)
