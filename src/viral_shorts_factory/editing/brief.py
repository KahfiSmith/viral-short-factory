"""Edit brief generator for content profiles (docs/03 §11, docs/05 M9)."""

from __future__ import annotations

from pathlib import Path

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetCandidate
from viral_shorts_factory.domain.concept import Concept
from viral_shorts_factory.domain.project import Project
from viral_shorts_factory.domain.script import Script
from viral_shorts_factory.domain.storyboard import Storyboard
from viral_shorts_factory.ranking.scoring import CandidateScore


def generate_edit_brief(
    project: Project,
    concept: Concept,
    script: Script,
    storyboard: Storyboard,
    selected_assets: dict[str, tuple[AssetCandidate, CandidateScore]],
    config: AppConfig,
    selected_source_paths: dict[str, list[str] | str] | None = None,
    selected_media_assets: dict[str, list[tuple[AssetCandidate, CandidateScore, str]]]
    | None = None,
) -> str:
    """Generate Markdown edit brief (edit_brief.md) for video-use."""
    lines: list[str] = []
    selected_source_paths = selected_source_paths or {}
    selected_media_assets = selected_media_assets or {}

    lines.append(f"# Edit Brief: {concept.title}")
    lines.append("")
    lines.append(f"**Project ID:** {project.project_id}")
    lines.append(f"**Profile:** {project.profile}")
    lines.append(f"**Platform:** {project.platform}")
    lines.append(f"**Language:** {project.language}")
    lines.append(f"**Target Duration:** ~{script.target_duration_seconds} seconds")
    lines.append(f"**Aspect Ratio:** {config.defaults.aspect_ratio} (vertical)")
    lines.append("")

    lines.append("## Executive Concept")
    lines.append(f"- **Premise:** {concept.premise}")
    lines.append(f"- **Hook:** {concept.hook}")
    lines.append(f"- **Mechanism:** {concept.comedy_mechanism}")
    lines.append(f"- **Payoff:** {concept.payoff}")
    lines.append("")

    lines.append("## Pacing & Editing Guidelines (Football Comedy)")
    lines.append("- **Hook:** Instant visual engagement within 1–2 seconds.")
    lines.append("- **Cuts:** Fast-paced cuts; match visual beats to narration.")
    lines.append(
        "- **Subtitles:** Large, clear burned subtitles in lower/mid frame; "
        "do not cover faces or football action."
    )
    lines.append(
        "- **Structure:** Expectation vs Reality flow with distinct pause before reaction/payoff."
    )
    lines.append("")

    lines.append("## Storyboard & Source Asset Mapping")
    lines.append("")

    for scene in storyboard.scenes:
        lines.append(f"### Scene {scene.order:02d}: `{scene.scene_id}` ({scene.purpose})")
        lines.append(f"- **Duration:** {scene.target_duration_seconds:.1f}s")
        lines.append(f'- **Spoken Text:** "{scene.spoken_text}"')
        lines.append(f"- **Visual Intent:** {scene.visual_intent}")

        selected = selected_assets.get(scene.scene_id)
        media_selected = selected_media_assets.get(scene.scene_id)
        if media_selected:
            lines.append("- **Selected Sources:**")
            for cand, score, path in media_selected:
                lines.append(
                    f"  - `{path}` ({cand.media_type.value}; "
                    f"Provider: {cand.provider} ID: {cand.provider_asset_id}; "
                    f"Score: {score.total:.2f})"
                )
        elif selected:
            cand, score = selected
            configured_path = selected_source_paths.get(scene.scene_id)
            if isinstance(configured_path, list):
                filename = configured_path[0]
            else:
                filename = configured_path or (
                    f"sources/{scene.scene_id}_{cand.provider}_{cand.provider_asset_id}.mp4"
                )
            lines.append(f"- **Selected Source:** `{filename}`")
            lines.append(f"  - Provider: {cand.provider} (ID: {cand.provider_asset_id})")
            lines.append(f"  - Score: {score.total:.2f}")
        else:
            lines.append("- **Selected Source:** *None selected*")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_edit_brief(content: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
