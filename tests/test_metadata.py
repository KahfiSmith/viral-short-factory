"""Tests for metadata file generation (Milestone 12)."""

from __future__ import annotations

from pathlib import Path

from viral_shorts_factory.domain.concept import Concept
from viral_shorts_factory.metadata.generator import generate_metadata_files


def test_generate_metadata_files(tmp_path: Path):
    concept = Concept(
        project_id="proj_1",
        title="Kiper Tarkam Neuer",
        premise="Kiper tarkam gaya neuer.",
        hook="Kiper gaya neuer.",
        comedy_mechanism="expectation_vs_reality",
        payoff="Gagal total.",
    )

    meta_dir = tmp_path / "metadata"
    result = generate_metadata_files(concept, meta_dir)

    assert result["title"].is_file()
    assert result["title"].read_text(encoding="utf-8").strip() == "Kiper Tarkam Neuer"

    assert result["description"].is_file()
    assert "Kiper tarkam gaya neuer." in result["description"].read_text(encoding="utf-8")

    assert result["hashtags"].is_file()
    assert "#shorts" in result["hashtags"].read_text(encoding="utf-8")
