"""Tests for downloader and source manifest (Milestone 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from viral_shorts_factory.assets.downloader import (
    Downloader,
    DownloadError,
    build_manifest,
    manifest_from_json,
)
from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetCandidate, DownloadVariant, RightsStatus


def test_manifest_serialization():
    cand = AssetCandidate(
        candidate_id="pexels:123",
        provider="pexels",
        provider_asset_id="123",
        query="soccer",
        rights_status=RightsStatus.PROVIDER_LICENSED,
    )
    from viral_shorts_factory.assets.downloader import DownloadedAsset
    from viral_shorts_factory.assets.probe import ProbeResult

    dl = DownloadedAsset(
        asset_id="asset_01",
        candidate_id="pexels:123",
        local_path="sources/scene_001_pexels_123.mp4",
        sha256="dummy_hash",
        bytes=100,
        probe=ProbeResult(
            duration_seconds=5.0,
            width=1080,
            height=1920,
            fps=30.0,
            video_codec="h264",
            has_audio=False,
        ),
    )

    manifest = build_manifest("proj_1", [("scene_001", cand, dl)])
    json_str = manifest.to_json()
    loaded = manifest_from_json(json_str)

    assert loaded.project_id == "proj_1"
    assert len(loaded.assets) == 1
    assert loaded.assets[0].scene_id == "scene_001"
    assert loaded.assets[0].provider == "pexels"


def test_download_candidate_http_rejected(config: AppConfig, tmp_path: Path):
    downloader = Downloader(config)
    cand = AssetCandidate(
        candidate_id="test:1",
        provider="test",
        provider_asset_id="1",
        query="test",
        download_variants=[
            DownloadVariant(
                url="http://insecure.com/video.mp4",
                width=1080,
                height=1920,
                file_type="video/mp4",
            )
        ],
    )

    with pytest.raises(DownloadError, match="HTTPS"):
        downloader.download_candidate(cand, "scene_001", tmp_path)
