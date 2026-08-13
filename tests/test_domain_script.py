"""Script domain model tests."""

from __future__ import annotations

import pytest

from viral_shorts_factory.domain.script import (
    Beat,
    BeatType,
    Script,
    ScriptError,
    script_from_json,
    script_to_json,
    validate_script,
)


def _script(**overrides) -> Script:
    params = dict(
        schema_version="1.0",
        target_duration_seconds=28.0,
        beats=[
            Beat(id="beat_001", type=BeatType.HOOK, text="Hook text.", estimated_seconds=5.0),
            Beat(id="beat_002", type=BeatType.PAYOFF, text="Payoff.", estimated_seconds=8.0),
        ],
    )
    params.update(overrides)
    return Script(**params)


def test_valid_script() -> None:
    script = _script()
    validate_script(script)
    assert len(script.beats) == 2


def test_empty_beats_rejected() -> None:
    with pytest.raises(ValueError):  # pydantic min_length=1
        _script(beats=[])


def test_duplicate_beat_ids_rejected() -> None:
    script = _script(
        beats=[
            Beat(id="same", type=BeatType.HOOK, text="a", estimated_seconds=5.0),
            Beat(id="same", type=BeatType.PAYOFF, text="b", estimated_seconds=6.0),
        ]
    )
    with pytest.raises(ScriptError, match="unique"):
        validate_script(script)


def test_estimated_seconds_ge_one() -> None:
    with pytest.raises(ValueError):  # pydantic ge=1
        _script(beats=[Beat(id="b1", type=BeatType.HOOK, text="a", estimated_seconds=0.5)])


def test_round_trip_json() -> None:
    script = _script()
    loaded = script_from_json(script_to_json(script))
    assert loaded == script


def test_invalid_json_rejected() -> None:
    with pytest.raises(ScriptError, match="invalid script"):
        script_from_json("{not json")
