"""Downloaded asset, manifest models, and downloader (docs/03 §8-9, docs/05 M8)."""

from __future__ import annotations

import json
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from viral_shorts_factory.assets.hashing import sha256_file
from viral_shorts_factory.assets.probe import ProbeError, ProbeResult, probe_video
from viral_shorts_factory.config.models import AppConfig, DownloadLimits
from viral_shorts_factory.domain.assets import AssetCandidate, MediaType, RightsStatus

SCHEMA_VERSION = "1.0"
_IMAGE_CODECS = frozenset({"bmp", "gif", "jpeg2000", "jpegls", "mjpeg", "png", "tiff", "webp"})


class DownloadError(Exception):
    """Raised when asset download or validation fails."""


class ManifestError(Exception):
    """Raised when manifest operation fails."""


class DownloadedAsset(BaseModel):
    """A downloaded and validated local asset record (docs/03 §8)."""

    asset_id: str
    candidate_id: str
    local_path: str
    sha256: str
    bytes: int
    probe: ProbeResult


class ManifestItem(BaseModel):
    """An entry in source_manifest.json (docs/03 §9)."""

    scene_id: str
    asset_id: str
    provider: str
    provider_asset_id: str
    media_type: MediaType = MediaType.VIDEO
    source_page_url: str | None = None
    contributor_name: str | None = None
    query: str
    rights_status: RightsStatus
    downloaded_at: str
    local_path: str
    sha256: str


class SourceManifest(BaseModel):
    """Source manifest document mapping selected assets to scenes (docs/03 §9)."""

    schema_version: str = SCHEMA_VERSION
    project_id: str
    assets: list[ManifestItem] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2) + "\n"


def manifest_from_json(text: str) -> SourceManifest:
    try:
        return SourceManifest.model_validate(json.loads(text))
    except Exception as exc:
        raise ManifestError(f"invalid source manifest: {exc}") from exc


class Downloader:
    """Downloader enforcing limits, HTTPS, SHA-256, ffprobe, and stable local path."""

    def __init__(self, config: AppConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self.limits: DownloadLimits = config.downloads
        self._client = client

    def download_candidate(
        self,
        candidate: AssetCandidate,
        scene_id: str,
        destination_dir: Path,
    ) -> DownloadedAsset:
        """Download candidate variant into destination_dir with stable filename."""
        if not candidate.download_variants:
            raise DownloadError(f"candidate {candidate.candidate_id} has no download variants")

        # Pick highest resolution variant
        variant = max(candidate.download_variants, key=lambda v: v.width * v.height)
        url = variant.url
        if not url.startswith("https://"):
            raise DownloadError(f"download URL must be HTTPS: {url}")

        destination_dir.mkdir(parents=True, exist_ok=True)
        is_image = candidate.media_type == MediaType.IMAGE or variant.file_type.lower().startswith(
            "image/"
        )
        ext = ".jpg" if is_image else ".mp4"
        filename = f"{scene_id}_{candidate.provider}_{candidate.provider_asset_id}{ext}"
        target_path = destination_dir / filename

        max_bytes = self.limits.max_file_size_mb * 1024 * 1024

        close_client = self._client is None
        client = self._client or httpx.Client(timeout=float(self.limits.timeout_seconds))

        try:
            with client.stream("GET", url, follow_redirects=True) as response:
                if response.status_code != 200:
                    raise DownloadError(
                        f"download failed with status {response.status_code} for {url}"
                    )
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type and content_type != "application/octet-stream":
                    expected_prefix = "image/" if is_image else "video/"
                    if not content_type.startswith(expected_prefix):
                        raise DownloadError(
                            f"invalid content-type for {candidate.media_type}: {content_type}"
                        )

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise DownloadError(
                        f"file size {content_length} exceeds limit {max_bytes} bytes"
                    )

                fd, tmp_name = tempfile.mkstemp(
                    dir=destination_dir, prefix=".download_", suffix=".tmp"
                )
                downloaded_bytes = 0
                try:
                    with open(fd, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            downloaded_bytes += len(chunk)
                            if downloaded_bytes > max_bytes:
                                raise DownloadError(
                                    f"download exceeded size limit of {max_bytes} bytes"
                                )
                            f.write(chunk)
                    tmp_path = Path(tmp_name)
                    tmp_path.replace(target_path)
                except BaseException:
                    Path(tmp_name).unlink(missing_ok=True)
                    raise
        finally:
            if close_client:
                client.close()

        sha256 = sha256_file(target_path)

        try:
            probe_result = probe_video(target_path)
        except ProbeError as exc:
            target_path.unlink(missing_ok=True)
            raise DownloadError(f"downloaded file failed media validation: {exc}") from exc

        if is_image:
            if probe_result.video_codec.lower() not in _IMAGE_CODECS:
                target_path.unlink(missing_ok=True)
                raise DownloadError(
                    f"downloaded file is not a supported image: {probe_result.video_codec}"
                )
            probe_result = ProbeResult(
                duration_seconds=0.0,
                width=probe_result.width,
                height=probe_result.height,
                fps=0.0,
                video_codec=probe_result.video_codec,
                has_audio=False,
            )

        asset_id = f"asset_{secrets.token_hex(8)}"
        return DownloadedAsset(
            asset_id=asset_id,
            candidate_id=candidate.candidate_id,
            local_path=str(target_path),
            sha256=sha256,
            bytes=downloaded_bytes,
            probe=probe_result,
        )


def build_manifest(
    project_id: str,
    items: list[tuple[str, AssetCandidate, DownloadedAsset]],
    now: datetime | None = None,
) -> SourceManifest:
    """Build a SourceManifest from (scene_id, candidate, downloaded_asset) tuples."""
    timestamp = (now or datetime.now(UTC)).isoformat()
    manifest_items: list[ManifestItem] = []
    for scene_id, cand, dl in items:
        manifest_items.append(
            ManifestItem(
                scene_id=scene_id,
                asset_id=dl.asset_id,
                provider=cand.provider,
                provider_asset_id=cand.provider_asset_id,
                media_type=cand.media_type,
                source_page_url=cand.source_page_url,
                contributor_name=cand.contributor_name,
                query=cand.query,
                rights_status=cand.rights_status,
                downloaded_at=timestamp,
                local_path=dl.local_path,
                sha256=dl.sha256,
            )
        )
    return SourceManifest(project_id=project_id, assets=manifest_items)
