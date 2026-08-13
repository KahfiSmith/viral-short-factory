"""Pexels footage provider (official API, docs/04-PROVIDER-INTEGRATIONS §2).

Adapter responsibilities:
- GET https://api.pexels.com/v1/videos/search with Authorization header;
- timeout + bounded retry (429/5xx/transport errors), permanent on 4xx auth;
- parse the raw response into private models (never exposed to domain code);
- filter to mp4 variants, sort by height desc, drop candidates below
  minimum_height;
- emit normalized AssetCandidate objects.

The API key is read from the configured environment variable at construction
and is never logged or serialized.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from typing import TYPE_CHECKING, Annotated

import httpx
from pydantic import BaseModel, BeforeValidator

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import (
    AssetCandidate,
    AssetSearchRequest,
    DownloadVariant,
    RightsStatus,
)
from viral_shorts_factory.providers.base import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)

if TYPE_CHECKING:
    from viral_shorts_factory.providers.base import (  # noqa: F401 (protocol conformance)
        FootageProvider,
    )

PEXELS_BASE_URL = "https://api.pexels.com/v1"
DEFAULT_TIMEOUT = 30.0
MAX_BACKOFF_SECONDS = 8.0


class ProviderConfigError(Exception):
    """Raised when a provider's API key configuration is missing/invalid."""


# ---- Private Pexels response models (never leave this module) ---------------


def _to_int(value: object) -> int | None:
    """Coerce str/int/None to int; Pexels returns numeric fields as strings."""
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


IntField = Annotated[int, BeforeValidator(_to_int)]
FloatField = Annotated[float, BeforeValidator(_to_float)]


class _PexelsVideoFile(BaseModel):
    id: IntField = 0
    quality: str | None = None
    file_type: str = ""
    width: IntField | None = None
    height: IntField | None = None
    link: str = ""


class _PexelsUser(BaseModel):
    id: IntField = 0
    name: str = ""
    url: str = ""


class _PexelsVideo(BaseModel):
    id: IntField = 0
    width: IntField | None = None
    height: IntField | None = None
    duration: FloatField | None = None
    url: str | None = None
    image: str | None = None
    video_files: list[_PexelsVideoFile] = []
    user: _PexelsUser | None = None


class _PexelsSearchResponse(BaseModel):
    videos: list[_PexelsVideo] = []


class PexelsProvider:
    """Pexels video search adapter."""

    name = "pexels"

    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        *,
        per_page: int = 20,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        self.per_page = per_page
        self.max_attempts = max_attempts

    @classmethod
    def from_config(cls, config: AppConfig, env: dict[str, str] | None = None) -> PexelsProvider:
        """Build a provider from config; raises if the key env var is unset."""
        provider_cfg = config.get_provider("pexels")
        if provider_cfg is None:
            raise ProviderConfigError("pexels provider is disabled or not configured")
        api_key = (env if env is not None else os.environ).get(provider_cfg.api_key_env or "")
        if not api_key:
            raise ProviderConfigError(
                f"pexels API key not set (expected env var {provider_cfg.api_key_env})"
            )
        return cls(api_key, per_page=provider_cfg.per_page)

    async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
        """Search Pexels for videos or photos and return normalized candidates."""
        from viral_shorts_factory.domain.assets import MediaType

        params = {
            "query": request.query,
            "orientation": request.orientation,
            "size": "medium",
            "locale": request.locale,
            "per_page": str(request.max_results or self.per_page),
        }
        endpoint = "/search" if request.media_type == MediaType.IMAGE else "/videos/search"
        response = await self._request_with_retry(endpoint, params)
        try:
            data = response.json()
        except Exception as exc:
            raise ProviderResponseError(f"invalid Pexels response: {exc}") from exc

        if request.media_type == MediaType.IMAGE:
            photos = data.get("photos", [])
            candidates: list[AssetCandidate] = []
            for photo in photos:
                src = photo.get("src", {})
                img_url = src.get("original") or src.get("large2x") or src.get("large")
                if not img_url:
                    continue
                candidates.append(
                    AssetCandidate(
                        candidate_id=f"pexels:photo:{photo['id']}",
                        provider="pexels",
                        provider_asset_id=str(photo["id"]),
                        media_type=MediaType.IMAGE,
                        source_page_url=photo.get("url"),
                        preview_url=src.get("medium"),
                        download_variants=[
                            DownloadVariant(
                                url=img_url,
                                width=photo.get("width", 1080),
                                height=photo.get("height", 1920),
                                file_type="image/jpeg",
                            )
                        ],
                        width=photo.get("width"),
                        height=photo.get("height"),
                        tags=[
                            token
                            for token in str(photo.get("alt") or "").lower().split()
                            if token.isalnum()
                        ],
                        contributor_name=photo.get("photographer"),
                        query=request.query,
                        rights_status=RightsStatus.PROVIDER_LICENSED,
                    )
                )
            return candidates

        try:
            raw = _PexelsSearchResponse.model_validate(data)
        except Exception as exc:
            raise ProviderResponseError(f"invalid Pexels response: {exc}") from exc
        return self._map_candidates(raw.videos, request)

    # ---- Internals ----------------------------------------------------------

    async def _request_with_retry(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        """GET search with bounded retry on 429/5xx/transport errors."""
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.get(
                    f"{PEXELS_BASE_URL}{endpoint}",
                    params=params,
                    headers={"Authorization": self.api_key},
                )
            except httpx.TransportError as exc:
                if attempt >= self.max_attempts:
                    raise ProviderServerError(f"pexels unreachable: {exc}") from exc
                await self._backoff(attempt)
                continue

            if response.status_code == 401 or response.status_code == 403:
                raise ProviderAuthError(
                    f"pexels rejected the API key (HTTP {response.status_code})"
                )
            if response.status_code == 429:
                if attempt >= self.max_attempts:
                    raise ProviderRateLimitError("pexels rate limited after retries")
                await self._backoff(attempt, retry_after=response.headers.get("retry-after"))
                continue
            if response.status_code >= 500:
                if attempt >= self.max_attempts:
                    raise ProviderServerError(
                        "pexels server error "
                        f"(HTTP {response.status_code}) after {attempt} attempts"
                    )
                await self._backoff(attempt)
                continue
            if response.status_code != 200:
                raise ProviderResponseError(f"pexels unexpected status {response.status_code}")
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
        self, videos: list[_PexelsVideo], request: AssetSearchRequest
    ) -> list[AssetCandidate]:
        """Normalize raw Pexels videos into domain AssetCandidates."""
        candidates: list[AssetCandidate] = []
        for video in videos:
            mp4 = [
                f
                for f in video.video_files
                if f.file_type == "video/mp4" and f.width is not None and f.height is not None
            ]
            if not mp4:
                continue  # no usable variant — skip
            mp4.sort(key=lambda f: f.height or 0, reverse=True)
            best = mp4[0]
            if request.minimum_height and (best.height or 0) < request.minimum_height:
                continue

            variants = [
                DownloadVariant(
                    url=f.link,
                    width=f.width or 0,
                    height=f.height or 0,
                    file_type=f.file_type,
                )
                for f in mp4
            ]
            candidates.append(
                AssetCandidate(
                    candidate_id=f"pexels:{video.id}",
                    provider=self.name,
                    provider_asset_id=str(video.id),
                    source_page_url=video.url,
                    preview_url=video.image,
                    download_variants=variants,
                    width=best.width,
                    height=best.height,
                    duration_seconds=video.duration,
                    contributor_name=video.user.name if video.user else None,
                    query=request.query,
                    rights_status=RightsStatus.PROVIDER_LICENSED,
                    raw_metadata_hash=self._raw_hash(video),
                )
            )
        return candidates

    @staticmethod
    def _raw_hash(video: _PexelsVideo) -> str:
        """Stable hash of the raw provider item for provenance."""
        canonical = json.dumps(video.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
