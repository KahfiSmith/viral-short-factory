"""football_comedy profile tests."""

from __future__ import annotations

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import Beat, BeatType, Script
from viral_shorts_factory.domain.storyboard import validate_storyboard, validate_storyboard_target
from viral_shorts_factory.profiles.football_comedy import (
    build_script_fixture,
    build_storyboard_from_script,
    generate_queries,
)

PROFILE = ProfileConfig(min_duration_seconds=18, max_duration_seconds=35, locale="id-ID")


def test_generate_queries_three_variants() -> None:
    queries = generate_queries(BeatType.HOOK, "amateur keeper on pitch")
    assert len(queries) == 3
    assert queries[0] == "amateur keeper on pitch"
    assert len(set(queries)) == 3


def test_build_storyboard_from_script() -> None:
    script = Script(
        schema_version="1.0",
        target_duration_seconds=28.0,
        beats=[
            Beat(id="b1", type=BeatType.HOOK, text="Hook.", estimated_seconds=4.0),
            Beat(id="b2", type=BeatType.SETUP, text="Setup.", estimated_seconds=7.0),
            Beat(id="b3", type=BeatType.ESCALATION, text="Escalate.", estimated_seconds=9.0),
            Beat(id="b4", type=BeatType.PAYOFF, text="Payoff.", estimated_seconds=8.0),
        ],
    )
    storyboard = build_storyboard_from_script(script, PROFILE)
    assert len(storyboard.scenes) == 4
    assert [s.purpose for s in storyboard.scenes] == [
        BeatType.HOOK,
        BeatType.SETUP,
        BeatType.ESCALATION,
        BeatType.PAYOFF,
    ]
    assert [s.order for s in storyboard.scenes] == [1, 2, 3, 4]
    assert all(len(s.queries) == 3 for s in storyboard.scenes)
    assert all("portrait" in s.constraints.orientation for s in storyboard.scenes)
    assert all(s.constraints.min_height == 1080 for s in storyboard.scenes)

    validate_storyboard(storyboard, PROFILE)
    validate_storyboard_target(storyboard, 28.0)


def test_storyboard_total_matches_script() -> None:
    script = build_script_fixture("kiper tarkam", 28.0)
    storyboard = build_storyboard_from_script(script, PROFILE)
    total = sum(s.target_duration_seconds for s in storyboard.scenes)
    assert abs(total - 28.0) < 0.01


def test_build_script_fixture() -> None:
    script = build_script_fixture("kiper tarkam merasa Neuer", 28.0)
    assert len(script.beats) == 4
    assert script.beats[0].type == BeatType.HOOK
    assert script.target_duration_seconds == 28.0
