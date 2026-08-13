"""Local asset library service (docs/04 §1, docs/02 §4 assets/library.py).

Wraps the AssetLibraryRepository with file hashing + ffprobe metadata and the
local-first search seam: the orchestrator queries the local library before any
network provider, so previously registered assets are reused without a network
call when a tag/category match suffices.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from viral_shorts_factory.assets.hashing import sha256_file
from viral_shorts_factory.assets.probe import ProbeError, probe_video
from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import (
    AssetCandidate,
    AssetSearchRequest,
    RightsStatus,
)
from viral_shorts_factory.persistence.repositories import (
    AssetLibraryEntry,
    AssetLibraryRepository,
    DatabaseConnection,
)


class AssetLibraryError(Exception):
    """Raised when a file cannot be registered into the library."""


class AssetLibrary:
    """Register, search, and reuse local video assets."""

    def __init__(self, conn: DatabaseConnection, config: AppConfig | None = None) -> None:
        self._repo = AssetLibraryRepository(conn)
        self.config = config

    def register(
        self,
        path: Path,
        *,
        category: str | None = None,
        tags: list[str] | None = None,
        provider: str | None = None,
        provider_asset_id: str | None = None,
        source_page_url: str | None = None,
        rights_status: RightsStatus | str = RightsStatus.UNVERIFIED,
    ) -> AssetLibraryEntry:
        """Hash + probe + store a local video; idempotent on identical SHA-256.

        A file registered without provider/source metadata stays UNVERIFIED and
        is never auto-selectable (docs/07 §4).
        """
        path = path.expanduser().resolve()
        if not path.is_file():
            raise AssetLibraryError(f"not a file: {path}")

        sha256 = sha256_file(path)
        existing = self._repo.find_by_sha256(sha256)
        if existing is not None:
            return existing  # duplicate prevention — no second row

        try:
            probe = probe_video(path)
        except ProbeError as exc:
            raise AssetLibraryError(f"cannot register {path}: {exc}") from exc

        normalized_tags = [t.strip().lower() for t in (tags or []) if t.strip()]
        entry = AssetLibraryEntry(
            asset_id=f"asset_{secrets.token_hex(8)}",
            local_path=str(path),
            sha256=sha256,
            category=category,
            tags=normalized_tags,
            width=probe.width,
            height=probe.height,
            duration_seconds=probe.duration_seconds,
            orientation=_orientation(probe.width, probe.height),
            provider=provider,
            provider_asset_id=provider_asset_id,
            source_page_url=source_page_url,
            rights_status=str(
                rights_status.value if isinstance(rights_status, RightsStatus) else rights_status
            ),
        )
        self._repo.register(entry)
        return entry

    def find_by_sha256(self, sha256: str) -> AssetLibraryEntry | None:
        return self._repo.find_by_sha256(sha256)

    def get(self, asset_id: str) -> AssetLibraryEntry | None:
        return self._repo.get(asset_id)

    def search(
        self, *, category: str | None = None, tags: list[str] | None = None
    ) -> list[AssetLibraryEntry]:
        normalized = [t.strip().lower() for t in (tags or []) if t.strip()]
        return self._repo.search(category=category, tags=normalized or None)

    def mark_used(self, asset_id: str, project_id: str, scene_id: str | None = None) -> None:
        self._repo.mark_used(asset_id, project_id, scene_id)


def local_first_search(library: AssetLibrary, request: AssetSearchRequest) -> list[AssetCandidate]:
    """Search the local library before network providers.

    Best-effort token-overlap match: an entry is returned when any of its tags
    shares a token with the query. Returns up to ``max_results`` candidates as
    AssetCandidate so downstream selection treats local and remote uniformly.
    """
    query_tokens = {t for t in request.query.lower().split() if t}
    scored_entries: list[tuple[int, AssetLibraryEntry]] = []
    for entry in library.search():
        entry_tokens = {t for tag in entry.tags for t in tag.lower().split()}
        overlap = len(query_tokens & entry_tokens)
        if overlap > 0:
            scored_entries.append((overlap, entry))
    # Most-overlapping first; stable by asset_id.
    scored_entries.sort(key=lambda pair: (-pair[0], pair[1].asset_id))

    candidates: list[AssetCandidate] = []
    for _overlap, entry in scored_entries[: request.max_results]:
        candidates.append(
            AssetCandidate(
                candidate_id=f"local:{entry.asset_id}",
                provider="local",
                provider_asset_id=entry.asset_id,
                source_page_url=entry.source_page_url,
                preview_url=None,
                download_variants=[],
                width=entry.width,
                height=entry.height,
                duration_seconds=entry.duration_seconds,
                tags=list(entry.tags),
                contributor_name=None,
                query=request.query,
                rights_status=_rights(entry.rights_status),
            )
        )
    return candidates


def _orientation(width: int, height: int) -> str:
    if width == height:
        return "square"
    return "portrait" if height > width else "landscape"


def _rights(status: str) -> RightsStatus:
    try:
        return RightsStatus(status)
    except ValueError:
        return RightsStatus.UNVERIFIED
