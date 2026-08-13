"""facts content profile tests."""

from __future__ import annotations

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import Beat, BeatType, Script
from viral_shorts_factory.domain.storyboard import validate_storyboard, validate_storyboard_target
from viral_shorts_factory.profiles.base import get_builder, get_script_builder
from viral_shorts_factory.profiles.facts import (
    build_script_fixture,
    build_storyboard_from_script,
    generate_queries,
)

PROFILE = ProfileConfig(min_duration_seconds=15, max_duration_seconds=45, locale="id-ID")


def test_facts_queries_are_nature_themed() -> None:
    queries = generate_queries(BeatType.HOOK, "betta fish macro underwater", "betta fish")
    assert len(queries) == 3
    assert all("betta" in q or "fish" in q for q in queries)


def test_beta_fish_topic_normalizes_to_betta_queries() -> None:
    script = build_script_fixture("beta fish", 28.0)
    storyboard = build_storyboard_from_script(script, PROFILE, "beta fish")
    assert all("betta fish" in scene.visual_intent for scene in storyboard.scenes)
    assert all("beta fish" not in query for scene in storyboard.scenes for query in scene.queries)
    assert all("hook" not in scene.queries[0] for scene in storyboard.scenes)


def test_facts_storyboard_from_script() -> None:
    script = Script(
        schema_version="1.0",
        target_duration_seconds=28.0,
        beats=[
            Beat(id="b1", type=BeatType.HOOK, text="Tahukah kamu?", estimated_seconds=4.0),
            Beat(
                id="b2",
                type=BeatType.SETUP,
                text="Mereka hidup berkelompok.",
                estimated_seconds=7.0,
            ),
            Beat(
                id="b3", type=BeatType.ESCALATION, text="Strategi berburu.", estimated_seconds=9.0
            ),
            Beat(
                id="b4",
                type=BeatType.PAYOFF,
                text="Fakta paling mengejutkan.",
                estimated_seconds=8.0,
            ),
        ],
    )
    storyboard = build_storyboard_from_script(script, PROFILE, "ikan cupang")
    assert len(storyboard.scenes) == 4
    assert all(len(s.queries) == 3 for s in storyboard.scenes)
    assert all("portrait" in s.constraints.orientation for s in storyboard.scenes)
    validate_storyboard(storyboard, PROFILE)
    validate_storyboard_target(storyboard, 28.0)


def test_facts_registered_in_registry() -> None:
    assert get_builder("facts") is build_storyboard_from_script
    assert get_script_builder("facts") is build_script_fixture


def test_facts_script_fixture() -> None:
    script = build_script_fixture("kucing orange", 28.0)
    assert len(script.beats) == 5
    assert script.beats[0].type == BeatType.HOOK
    assert "kucing orange" in script.beats[0].text


def test_clownfish_topic_normalizes_to_species_specific_queries() -> None:
    script = build_script_fixture("ikan badut", 28.0)
    storyboard = build_storyboard_from_script(script, PROFILE, "ikan badut")

    assert all("clownfish" in scene.visual_intent for scene in storyboard.scenes)
    assert all("ikan badut" not in query for scene in storyboard.scenes for query in scene.queries)
    assert all(
        "clownfish" in query or "anemone" in query or "ocellaris" in query
        for scene in storyboard.scenes
        for query in scene.queries
    )


def test_lion_topic_normalizes_to_species_specific_queries() -> None:
    script = build_script_fixture("singa", 28.0)
    storyboard = build_storyboard_from_script(script, PROFILE, "singa")

    assert all("lion" in scene.visual_intent for scene in storyboard.scenes)
    assert all("singa" not in query for scene in storyboard.scenes for query in scene.queries)
    assert all("lion" in query for scene in storyboard.scenes for query in scene.queries)
