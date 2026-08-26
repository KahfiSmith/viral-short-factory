"""Unsplash photo provider (official API).

Adapter responsibilities:
- GET https://api.unsplash.com/search/photos with Authorization header;
- timeout + bounded retry (429/5xx/transport), permanent on 4xx auth;
- parse raw response into private models (never exposed to domain code);
- emit normalized AssetCandidate objects with MediaType.IMAGE.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import (
    AssetCandidate,
    AssetSearchRequest,
    DownloadVariant,
    MediaType,
    RightsStatus,
)
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

UNSPLASH_BASE_URL = "https://api.unsplash.com"


# ---- Private Unsplash response models (never leave this module) -------------


class _UnsplashUrls(BaseModel):
    raw: str | None = None
    full: str | None = None
    regular: str | None = None
    small: str | None = None
    thumb: str | None = None


class _UnsplashLinks(BaseModel):
    html: str = ""
    download_location: str | None = None


class _UnsplashUser(BaseModel):
    name: str = ""
    username: str = ""


class _UnsplashPhoto(BaseModel):
    id: str
    width: int = 0
    height: int = 0
    description: str | None = None
    alt_description: str | None = None
    urls: _UnsplashUrls
    links: _UnsplashLinks
    user: _UnsplashUser


class _UnsplashSearchResponse(BaseModel):
    total: int = 0
    results: list[_UnsplashPhoto] = []


class UnsplashProvider:
    """Unsplash image search adapter."""

    name = "unsplash"

    def __init__(
        self,
        access_key: str,
        client: httpx.AsyncClient | None = None,
        *,
        per_page: int = 20,
        max_attempts: int = 3,
    ) -> None:
        self.access_key = access_key
        self._client = client
        self.per_page = per_page
        self.max_attempts = max_attempts

    @classmethod
    def from_config(
        cls, config: AppConfig, env: dict[str, str] | None = None
    ) -> UnsplashProvider:
        provider_cfg = config.get_provider("unsplash")
        env_var = provider_cfg.api_key_env if provider_cfg else "UNSPLASH_ACCESS_KEY"
        key_name = env_var or "UNSPLASH_ACCESS_KEY"
        env_source = os.environ if env is None else env
        access_key = env_source.get(key_name)
        if not access_key:
            raise ProviderConfigError(
                f"missing Unsplash access key: env var '{key_name}' is not set"
            )
        per_page = provider_cfg.per_page if provider_cfg else 20
        return cls(access_key=access_key, per_page=per_page)

    async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
        """Search Unsplash photos and map to normalized AssetCandidate objects."""
        # Unsplash only provides images
        params = {
            "query": request.query,
            "per_page": min(request.max_results or self.per_page, 30),
            "orientation": "portrait" if request.orientation == "portrait" else "landscape",
        }
        headers = {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1",
        }

        url = f"{UNSPLASH_BASE_URL}/search/photos"
        data = await self._fetch_with_retry(url, params=params, headers=headers)
        return self._normalize(data, request)

    async def _fetch_with_retry(
        self, url: str, params: dict[str, object], headers: dict[str, str]
    ) -> dict[str, object]:
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
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
                            f"Unsplash transport error after {attempt} attempts: {exc}"
                        ) from exc
                    await self._sleep_backoff(attempt)
                    continue

                if resp.status_code in (401, 403):
                    raise ProviderAuthError(
                        f"Unsplash auth rejected (HTTP {resp.status_code}): {resp.text}"
                    )
                if resp.status_code == 429:
                    last_error = ProviderRateLimitError(
                        f"Unsplash rate limit hit (HTTP 429): {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue
                if resp.status_code >= 500:
                    last_error = ProviderServerError(
                        f"Unsplash server error HTTP {resp.status_code}: {resp.text}"
                    )
                    if attempt >= self.max_attempts:
                        raise last_error
                    await self._sleep_backoff(attempt)
                    continue
                if resp.status_code != 200:
                    raise ProviderResponseError(
                        f"Unsplash unexpected HTTP {resp.status_code}: {resp.text}"
                    )

                try:
                    return resp.json()  # type: ignore[no-any-return]
                except json.JSONDecodeError as exc:
                    raise ProviderResponseError(
                        f"Unsplash returned non-JSON body: {exc}"
                    ) from exc
        finally:
            if own_client:
                await client.aclose()

        if last_error:
            raise last_error
        raise ProviderServerError("Unsplash request failed with unknown error")

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = min(MAX_BACKOFF_SECONDS, (2 ** (attempt - 1)) + random.uniform(0, 0.5))  # noqa: S311
        await asyncio.sleep(delay)

    def _normalize(
        self, raw_data: dict[str, object], request: AssetSearchRequest
    ) -> list[AssetCandidate]:
        try:
            parsed = _UnsplashSearchResponse.model_validate(raw_data)
        except Exception as exc:
            raise ProviderResponseError(f"failed to parse Unsplash response: {exc}") from exc

        candidates: list[AssetCandidate] = []
        for photo in parsed.results:
            tags = [
                t.strip().lower()
                for t in (
                    (photo.description or "").split()
                    + (photo.alt_description or "").split()
                )
                if len(t.strip()) > 2
            ]

            # Best resolution download URL
            img_url = photo.urls.full or photo.urls.regular or photo.urls.raw
            if not img_url:
                continue

            variants = [
                DownloadVariant(
                    url=img_url,
                    width=photo.width,
                    height=photo.height,
                    file_type="image/jpeg",
                )
            ]

            raw_str = json.dumps(photo.model_dump(), sort_keys=True)
            meta_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

            candidates.append(
                AssetCandidate(
                    candidate_id=f"unsplash:{photo.id}",
                    provider=self.name,
                    provider_asset_id=photo.id,
                    media_type=MediaType.IMAGE,
                    source_page_url=photo.links.html or f"https://unsplash.com/photos/{photo.id}",
                    preview_url=photo.urls.small or photo.urls.thumb,
                    download_variants=variants,
                    width=photo.width,
                    height=photo.height,
                    duration_seconds=0.0,
                    tags=tags,
                    contributor_name=photo.user.name or photo.user.username,
                    query=request.query,
                    rights_status=RightsStatus.PROVIDER_LICENSED,
                    raw_metadata_hash=meta_hash,
                )
            )
        return candidates
