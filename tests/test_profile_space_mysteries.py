"""space_mysteries content profile tests."""

from __future__ import annotations

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import Beat, BeatType, Script
from viral_shorts_factory.domain.storyboard import validate_storyboard, validate_storyboard_target
from viral_shorts_factory.profiles.base import get_builder, get_script_builder
from viral_shorts_factory.profiles.space_mysteries import (
    build_script_fixture,
    build_storyboard_from_script,
    generate_queries,
)

PROFILE = ProfileConfig(min_duration_seconds=15, max_duration_seconds=45, locale="id-ID")


def test_generate_queries_three_variants() -> None:
    queries = generate_queries(BeatType.HOOK, "mysterious black hole in deep space", "black hole")
    assert len(queries) == 3
    assert queries[0] == "mysterious black hole in deep space"
    assert len(set(queries)) == 3


def test_queries_are_space_themed_and_topic_locked() -> None:
    queries = generate_queries(BeatType.SETUP, "planet mars distant orbit", "planet mars")
    assert len(queries) == 3
    assert "planet mars" in queries[0]
    assert all("planet mars" in q for q in queries[1:])


def test_queries_without_topic_are_generic_space() -> None:
    queries = generate_queries(BeatType.CTA, "serene starry sky", "")
    assert len(queries) == 3


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
    storyboard = build_storyboard_from_script(script, PROFILE, "black hole")
    assert len(storyboard.scenes) == 4
    assert all("black hole" in s.visual_intent for s in storyboard.scenes)
    assert all(len(s.queries) == 3 for s in storyboard.scenes)
    assert all(s.constraints.people_allowed is False for s in storyboard.scenes)
    assert all("portrait" in s.constraints.orientation for s in storyboard.scenes)

    validate_storyboard(storyboard, PROFILE)
    validate_storyboard_target(storyboard, 28.0)


def test_storyboard_total_matches_script() -> None:
    script = build_script_fixture("milky way", 28.0)
    storyboard = build_storyboard_from_script(script, PROFILE, "milky way")
    total = sum(s.target_duration_seconds for s in storyboard.scenes)
    assert abs(total - 28.0) < 0.01


def test_space_mysteries_registered_in_registry() -> None:
    assert get_builder("space_mysteries") is build_storyboard_from_script
    assert get_script_builder("space_mysteries") is build_script_fixture


def test_build_script_fixture() -> None:
    script = build_script_fixture("lubang hitam", 28.0)
    assert len(script.beats) == 5
    assert script.beats[0].type == BeatType.HOOK
    assert script.target_duration_seconds == 28.0
    assert "lubang hitam" in script.beats[0].text


def test_extract_english_topic_normalizes_aliases() -> None:
    from viral_shorts_factory.profiles.space_mysteries import _extract_english_topic

    cases = {
        "lubang hitam": "black hole",
        "bintang neutron": "neutron star",
        "materi gelap": "dark matter",
        "lubang cacing": "wormhole",
        "bima sakti": "milky way",
        "tata surya": "solar system",
        "matahari": "sun",
        "bulan": "moon",
        "merkurius": "mercury",
        "planet mars": "mars",
        "planet jupiter": "jupiter",
        "planet saturnus": "saturn",
        "planet neptunus": "neptune",
        "komet": "comet",
        "gerhana": "eclipse",
        "badai matahari": "solar flare",
        "gravitasi": "gravity",
        "stasiun luar angkasa": "space station",
        "astronot": "astronaut",
        "teleskop": "telescope",
        "teleskop james webb": "james webb",
        "penjelajah mars": "mars rover",
        "kehidupan alien": "extraterrestrial life",
        "galaksi": "galaxy",
    }
    for raw, expected in cases.items():
        assert _extract_english_topic(raw) == expected, (raw, expected)


def test_unknown_topic_passes_through() -> None:
    from viral_shorts_factory.profiles.space_mysteries import _extract_english_topic

    assert _extract_english_topic("sebuah misteri baru") == "sebuah misteri baru"


def test_queries_never_contain_Indonesian_topic() -> None:
    for raw in ("lubang hitam", "matahari", "planet mars", "bintang neutron"):
        script = build_script_fixture(raw, 28.0)
        storyboard = build_storyboard_from_script(script, PROFILE, raw)
        for scene in storyboard.scenes:
            for query in scene.queries:
                assert "lubang hitam" not in query
                assert "matahari" not in query
                assert "planet mars" not in query
                assert "bintang neutron" not in query