"""Metadata generator for output package (title, description, hashtags) (docs/03, docs/05 M12)."""

from __future__ import annotations

from pathlib import Path

from viral_shorts_factory.domain.concept import Concept


def generate_metadata_files(concept: Concept, destination_dir: Path) -> dict[str, Path]:
    """Generate title.txt, description.txt, and hashtags.txt into destination_dir."""
    destination_dir.mkdir(parents=True, exist_ok=True)

    title_file = destination_dir / "title.txt"
    title_file.write_text(f"{concept.title}\n", encoding="utf-8")

    desc_file = destination_dir / "description.txt"
    desc_content = f"{concept.premise}\n\n{concept.hook}\n"
    desc_file.write_text(desc_content, encoding="utf-8")

    hashtags_file = destination_dir / "hashtags.txt"
    # Basic default hashtags based on profile/topic
    tags = ["#shorts", "#football", "#sepakbola", "#tarkam", "#komedi", "#funny"]
    hashtags_file.write_text(" ".join(tags) + "\n", encoding="utf-8")

    return {
        "title": title_file,
        "description": desc_file,
        "hashtags": hashtags_file,
    }
