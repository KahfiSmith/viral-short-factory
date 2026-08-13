"""Storyboard domain model tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import BeatType
from viral_shorts_factory.domain.storyboard import (
    Scene,
    Storyboard,
    StoryboardError,
    storyboard_from_json,
    storyboard_to_json,
    validate_storyboard,
    validate_storyboard_target,
)

PROFILE = ProfileConfig(min_duration_seconds=18, max_duration_seconds=35, locale="id-ID")


def _scene(scene_id: str = "scene_001", order: int = 1, **overrides) -> Scene:
    params = dict(
        scene_id=scene_id,
        order=order,
        purpose=BeatType.HOOK,
        target_duration_seconds=5.0,
        spoken_text="Hook.",
        visual_intent="goalkeeper on field",
        queries=["goalkeeper field"],
    )
    params.update(overrides)
    return Scene(**params)


def test_example_storyboard_validates() -> None:
    example = Path(__file__).resolve().parents[1] / "examples" / "storyboard.example.json"
    storyboard = storyboard_from_json(example.read_text(encoding="utf-8"))
    validate_storyboard(storyboard, PROFILE)
    assert len(storyboard.scenes) == 2


def test_duplicate_scene_id_rejected() -> None:
    storyboard = Storyboard(scenes=[_scene("s1", 1), _scene("s1", 2, purpose=BeatType.PAYOFF)])
    with pytest.raises(StoryboardError, match="unique"):
        validate_storyboard(storyboard, PROFILE)


def test_non_sequential_orders_rejected() -> None:
    storyboard = Storyboard(scenes=[_scene("s1", 2), _scene("s2", 1)])
    with pytest.raises(StoryboardError, match="sequential"):
        validate_storyboard(storyboard, PROFILE)


def test_empty_queries_rejected_at_construction() -> None:
    # Pydantic enforces min_length=1 on queries; constructing empty must fail.
    with pytest.raises(ValueError):
        _scene("s1", 1, queries=[])


def test_target_duration_tolerance() -> None:
    storyboard = Storyboard(
        scenes=[
            _scene("s1", 1, target_duration_seconds=14.0),
            _scene("s2", 2, target_duration_seconds=14.0),
        ]
    )
    # Total 28 vs target 28 -> ok.
    validate_storyboard_target(storyboard, 28.0)
    # Total 28 vs target 20 -> outside ±2.0 tolerance.
    with pytest.raises(StoryboardError, match="outside target"):
        validate_storyboard_target(storyboard, 20.0)


def test_round_trip_json() -> None:
    storyboard = Storyboard(scenes=[_scene()])
    loaded = storyboard_from_json(storyboard_to_json(storyboard))
    assert loaded == storyboard
