"""Pixabay footage provider (official API, docs/04-PROVIDER-INTEGRATIONS §3).

Adapter responsibilities:
- GET https://pixabay.com/api/videos/ with the key as a query param;
- mandatory 24h cache of successful responses via CacheRepository;
- timeout + bounded retry (429/5xx/transport), permanent on auth errors;
- parse raw response into private models (never exposed to domain code);
- filter to mp4 variants, sort by height desc, drop below minimum_height;
- emit normalized AssetCandidate objects.

The cache key is sha256("pixabay|videos|<sorted query params>") and excludes the
API key itself. Only HTTP 200 responses are cached, so corrupt/error responses
are never stored.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import (
    AssetCandidate,
    AssetSearchRequest,
    DownloadVariant,
    RightsStatus,
)
from viral_shorts_factory.persistence.repositories import CacheRepository, DatabaseConnection
from viral_shorts_factory.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)
from viral_shorts_factory.providers.pexels import (
    DEFAULT_TIMEOUT,
    MAX_BACKOFF_SECONDS,
    ProviderConfigError,
)

if TYPE_CHECKING:
    from viral_shorts_factory.providers.base import (  # noqa: F401 (protocol conformance)
        FootageProvider,
    )

PIXABAY_BASE_URL = "https://pixabay.com/api/videos/"


# ---- Private Pixabay response models (never leave this module) --------------


class _PixabayVideoFile(BaseModel):
    type: str
    url: str
    width: int | None = None
    height: int | None = None
    size: int | None = None


class _PixabayVideo(BaseModel):
    id: int
    pageURL: str
    duration: int
    image: str
    videos: dict[str, _PixabayVideoFile]
    user: str = ""
    userImageURL: str = ""
    tags: str = ""


class _PixabayResponse(BaseModel):
    total: int = 0
    hits: list[_PixabayVideo] = []


class PixabayProvider:
    """Pixabay video search adapter with mandatory 24h cache."""

    name = "pixabay"

    def __init__(
        self,
        api_key: str,
        cache: CacheRepository,
        client: httpx.AsyncClient | None = None,
        *,
        per_page: int = 20,
        cache_ttl_hours: int = 24,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key
        self._cache = cache
        self._client = client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        self.per_page = per_page
        self.cache_ttl_hours = cache_ttl_hours
        self.max_attempts = max_attempts

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        conn: DatabaseConnection,
        env: dict[str, str] | None = None,
    ) -> PixabayProvider:
        """Build a provider from config + DB; raises if the key env var is unset."""
        provider_cfg = config.get_provider("pixabay")
        if provider_cfg is None:
            raise ProviderConfigError("pixabay provider is disabled or not configured")
        api_key = (env if env is not None else os.environ).get(provider_cfg.api_key_env or "")
        if not api_key:
            raise ProviderConfigError(
                f"pixabay API key not set (expected env var {provider_cfg.api_key_env})"
            )
        return cls(
            api_key,
            CacheRepository(conn),
            per_page=provider_cfg.per_page,
            cache_ttl_hours=provider_cfg.cache_ttl_hours or 24,
        )

    async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
        """Search Pixabay for videos or photos, honoring the 24h cache."""
        from viral_shorts_factory.domain.assets import MediaType

        is_image = request.media_type == MediaType.IMAGE
        params = {
            "q": request.query,
            "lang": request.locale,
            "safesearch": "true",
            "order": "popular",
            "category": "sports",
            "per_page": str(request.max_results or self.per_page),
        }
        if not is_image:
            params["video_type"] = "film"

        cache_key = self._cache_key(params)

        cached = self._cache.get(cache_key, now=datetime.now(UTC))
        if cached is not None:
            data = json.loads(cached.response_json)
        else:
            endpoint = "" if is_image else "/videos/"
            response = await self._request_with_retry(endpoint, params)
            try:
                data = response.json()
            except Exception as exc:
                raise ProviderResponseError(f"invalid Pixabay response: {exc}") from exc
            self._cache.set(
                cache_key,
                response.text,
                response.status_code,
                ttl_hours=self.cache_ttl_hours,
                now=datetime.now(UTC),
            )

        candidates: list[AssetCandidate] = []
        if is_image:
            for hit in data.get("hits", []):
                img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                if not img_url:
                    continue
                candidates.append(
                    AssetCandidate(
                        candidate_id=f"pixabay:photo:{hit['id']}",
                        provider="pixabay",
                        provider_asset_id=str(hit["id"]),
                        media_type=MediaType.IMAGE,
                        source_page_url=hit.get("pageURL"),
                        preview_url=hit.get("previewURL"),
                        download_variants=[
                            DownloadVariant(
                                url=img_url,
                                width=hit.get("imageWidth", 1080),
                                height=hit.get("imageHeight", 1920),
                                file_type="image/jpeg",
                            )
                        ],
                        width=hit.get("imageWidth"),
                        height=hit.get("imageHeight"),
                        contributor_name=hit.get("user"),
                        query=request.query,
                        rights_status=RightsStatus.PROVIDER_LICENSED,
                    )
                )
            return candidates

        raw = _parse_response(json.dumps(data))
        return self._map_candidates(raw, request)

    # ---- Internals ----------------------------------------------------------

    async def _request_with_retry(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        """GET API with bounded retry on 429/5xx/transport errors."""
        request_params = {**params, "key": self.api_key}
        url = f"{PIXABAY_BASE_URL}{endpoint}"
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.get(url, params=request_params)
            except httpx.TransportError as exc:
                if attempt >= self.max_attempts:
                    raise ProviderServerError(f"pixabay unreachable: {exc}") from exc
                await self._backoff(attempt)
                continue

            if response.status_code == 401 or response.status_code == 403:
                raise ProviderAuthError(
                    f"pixabay rejected the API key (HTTP {response.status_code})"
                )
            if response.status_code == 429:
                if attempt >= self.max_attempts:
                    raise ProviderRateLimitError("pixabay rate limited after retries")
                await self._backoff(attempt, retry_after=response.headers.get("retry-after"))
                continue
            if response.status_code >= 500:
                if attempt >= self.max_attempts:
                    raise ProviderServerError(
                        "pixabay server error "
                        f"(HTTP {response.status_code}) after {attempt} attempts"
                    )
                await self._backoff(attempt)
                continue
            if response.status_code != 200:
                raise ProviderResponseError(f"pixabay unexpected status {response.status_code}")
            return response

    async def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        """Bounded exponential backoff with jitter; honors Retry-After if valid."""
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = 0.0
        else:
            delay = min(2 ** (attempt - 1), MAX_BACKOFF_SECONDS)
        jitter = random.uniform(0, 0.5)  # noqa: S311 - backoff jitter, not security-sensitive
        await asyncio.sleep(delay + jitter)

    def _map_candidates(
        self, raw: _PixabayResponse, request: AssetSearchRequest
    ) -> list[AssetCandidate]:
        """Normalize raw Pixabay hits into domain AssetCandidates."""
        candidates: list[AssetCandidate] = []
        for video in raw.hits:
            files = [f for f in video.videos.values() if f.type == "video/mp4"]
            files = [f for f in files if f.width is not None and f.height is not None]
            if not files:
                continue
            files.sort(key=lambda f: f.height or 0, reverse=True)
            best = files[0]
            if request.minimum_height and (best.height or 0) < request.minimum_height:
                continue

            candidates.append(
                AssetCandidate(
                    candidate_id=f"pixabay:{video.id}",
                    provider=self.name,
                    provider_asset_id=str(video.id),
                    source_page_url=video.pageURL,
                    preview_url=video.image,
                    download_variants=[
                        DownloadVariant(
                            url=f.url,
                            width=f.width or 0,
                            height=f.height or 0,
                            file_type=f.type,
                        )
                        for f in files
                    ],
                    width=best.width,
                    height=best.height,
                    duration_seconds=float(video.duration),
                    tags=[t.strip() for t in video.tags.split(",") if t.strip()],
                    contributor_name=video.user or None,
                    query=request.query,
                    rights_status=RightsStatus.PROVIDER_LICENSED,
                    raw_metadata_hash=self._raw_hash(video),
                )
            )
        return candidates

    @staticmethod
    def _cache_key(params: dict[str, str]) -> str:
        """sha256("pixabay|videos|q=...&category=...") with sorted params.

        Excludes the API key; ordering-independent so equivalent requests share
        a key.
        """
        normalized = "&".join(f"{k}={params[k]}" for k in sorted(params))
        canonical = f"pixabay|videos|{normalized}"
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _raw_hash(video: _PixabayVideo) -> str:
        canonical = json.dumps(video.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _parse_response(text: str) -> _PixabayResponse:
    """Parse raw response text; raises ProviderResponseError on invalid JSON."""
    try:
        return _PixabayResponse.model_validate(json.loads(text))
    except Exception as exc:
        raise ProviderResponseError(f"invalid pixabay response: {exc}") from exc
