"""Domain models for footage assets (docs/03-DATA-CONTRACTS §5–6).

Provider response formats must never leak past the provider adapters; these are
the normalized shapes domain code consumes.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RightsStatus(StrEnum):
    """Provenance status of an asset."""

    PROVIDER_LICENSED = "PROVIDER_LICENSED"
    USER_OWNED = "USER_OWNED"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    ATTRIBUTION_REQUIRED = "ATTRIBUTION_REQUIRED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"


class DownloadVariant(BaseModel):
    """A concrete downloadable rendition of an asset."""

    url: str
    width: int
    height: int
    file_type: str


class MediaType(StrEnum):
    """Media type for asset candidates."""

    VIDEO = "video"
    IMAGE = "image"


class AssetCandidate(BaseModel):
    """A normalized footage/image candidate from any provider."""

    candidate_id: str
    provider: str
    provider_asset_id: str
    media_type: MediaType = MediaType.VIDEO
    source_page_url: str | None = None
    preview_url: str | None = None
    download_variants: list[DownloadVariant] = Field(default_factory=list)
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    tags: list[str] = Field(default_factory=list)
    contributor_name: str | None = None
    query: str
    rights_status: RightsStatus = RightsStatus.UNVERIFIED
    raw_metadata_hash: str | None = None


class AssetSearchRequest(BaseModel):
    """A provider-agnostic search request (docs/03 §5)."""

    scene_id: str
    query: str
    media_type: MediaType = MediaType.VIDEO
    locale: str = "en-US"
    orientation: str = "portrait"
    minimum_height: int = 1080
    max_results: int = 20
