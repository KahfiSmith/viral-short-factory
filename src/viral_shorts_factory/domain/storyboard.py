"""Storyboard model (docs/03-DATA-CONTRACTS §4)."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import BeatType

SCHEMA_VERSION = "1.0"

# Tolerance for total storyboard duration vs the script target.
DURATION_TOLERANCE = 0.10


class StoryboardError(Exception):
    """Raised when a storyboard is invalid."""


class SceneConstraints(BaseModel):
    """Asset constraints for a scene (docs/03 §4)."""

    orientation: str = "portrait_preferred"
    min_height: int = 1080
    min_duration_seconds: float = 2.0
    max_duration_seconds: float = 15.0
    people_allowed: bool = True


class Scene(BaseModel):
    """A single storyboard scene."""

    scene_id: str = Field(min_length=1)
    order: int = Field(ge=1)
    purpose: BeatType
    target_duration_seconds: float = Field(ge=0.5)
    spoken_text: str = Field(min_length=1)
    visual_intent: str = Field(min_length=1)
    queries: list[str] = Field(min_length=1)
    constraints: SceneConstraints = Field(default_factory=SceneConstraints)


class Storyboard(BaseModel):
    """The full scene list for a video."""

    schema_version: str = SCHEMA_VERSION
    scenes: list[Scene] = Field(min_length=1)


def validate_storyboard(storyboard: Storyboard, _profile: ProfileConfig | None = None) -> None:
    """Validate a storyboard; raises StoryboardError on problems.

    Profile duration bounds apply to the *total* video (checked by
    validate_storyboard_target), not to individual scenes — scenes are short
    segments of the whole.
    """
    ids = [s.scene_id for s in storyboard.scenes]
    if len(ids) != len(set(ids)):
        raise StoryboardError("scene ids must be unique")
    orders = [s.order for s in storyboard.scenes]
    if orders != sorted(orders) or len(set(orders)) != len(orders):
        raise StoryboardError("scene orders must be sequential and unique")


def validate_storyboard_target(storyboard: Storyboard, target_duration_seconds: float) -> None:
    """Check total storyboard duration is within tolerance of the target."""
    total = sum(s.target_duration_seconds for s in storyboard.scenes)
    tolerance = max(target_duration_seconds * DURATION_TOLERANCE, 1.0)
    if abs(total - target_duration_seconds) > tolerance:
        raise StoryboardError(
            "storyboard total "
            f"{total:.1f}s outside target {target_duration_seconds:.1f}s ±{tolerance:.1f}s"
        )


def storyboard_to_json(storyboard: Storyboard) -> str:
    return storyboard.model_dump_json(indent=2) + "\n"


def storyboard_from_json(text: str) -> Storyboard:
    try:
        return Storyboard.model_validate(json.loads(text))
    except Exception as exc:
        raise StoryboardError(f"invalid storyboard: {exc}") from exc


def storyboard_to_dict(storyboard: Storyboard) -> dict[str, object]:
    return storyboard.model_dump(mode="json")
