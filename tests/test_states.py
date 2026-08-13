"""Pipeline stage transition tests."""

from __future__ import annotations

import pytest

from viral_shorts_factory.domain.states import (
    FAILED_STAGES,
    TERMINAL_STAGES,
    InvalidTransitionError,
    Stage,
    is_failed,
    is_terminal,
    validate_transition,
)

EXPECTED_STATES = {
    "INIT",
    "BRIEF_READY",
    "CONCEPT_READY",
    "SCRIPT_READY",
    "STORYBOARD_READY",
    "ASSET_QUERIES_READY",
    "ASSETS_DISCOVERED",
    "ASSETS_SELECTED",
    "EDIT_BRIEF_READY",
    "EDIT_STRATEGY_PROPOSED",
    "AWAITING_EDIT_STRATEGY_APPROVAL",
    "EDITING",
    "QC",
    "COMPLETE",
    "FAILED_RETRYABLE",
    "FAILED_PERMANENT",
    "CANCELLED",
}


def test_all_states_present() -> None:
    assert {s.value for s in Stage} == EXPECTED_STATES


@pytest.mark.parametrize(
    ("from_stage", "to_stage"),
    [
        (Stage.INIT, Stage.BRIEF_READY),
        (Stage.BRIEF_READY, Stage.CONCEPT_READY),
        (Stage.STORYBOARD_READY, Stage.ASSET_QUERIES_READY),
        (Stage.AWAITING_EDIT_STRATEGY_APPROVAL, Stage.EDITING),
        (Stage.EDITING, Stage.QC),
        (Stage.QC, Stage.COMPLETE),
        (Stage.INIT, Stage.FAILED_PERMANENT),
        (Stage.ASSETS_SELECTED, Stage.CANCELLED),
    ],
)
def test_valid_transitions(from_stage: Stage, to_stage: Stage) -> None:
    validate_transition(from_stage, to_stage)


@pytest.mark.parametrize(
    ("from_stage", "to_stage"),
    [
        (Stage.INIT, Stage.COMPLETE),
        (Stage.INIT, Stage.EDITING),
        (Stage.COMPLETE, Stage.EDITING),
        (Stage.QC, Stage.INIT),
        (Stage.CANCELLED, Stage.INIT),
        (Stage.FAILED_PERMANENT, Stage.INIT),
        (Stage.INIT, Stage.AWAITING_EDIT_STRATEGY_APPROVAL),
    ],
)
def test_invalid_transitions_rejected(from_stage: Stage, to_stage: Stage) -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition(from_stage, to_stage)


def test_terminal_and_failed_helpers() -> None:
    assert TERMINAL_STAGES == {Stage.COMPLETE, Stage.FAILED_PERMANENT, Stage.CANCELLED}
    assert FAILED_STAGES == {Stage.FAILED_RETRYABLE, Stage.FAILED_PERMANENT}
    assert all(is_terminal(s) for s in TERMINAL_STAGES)
    assert all(is_failed(s) for s in FAILED_STAGES)
    assert not is_terminal(Stage.EDITING)
    assert not is_failed(Stage.EDITING)


def test_retryable_can_resume() -> None:
    # FAILED_RETRYABLE may return to the stage it failed from.
    validate_transition(Stage.FAILED_RETRYABLE, Stage.ASSETS_DISCOVERED)
    with pytest.raises(InvalidTransitionError):
        validate_transition(Stage.FAILED_RETRYABLE, Stage.COMPLETE)
