"""Pipeline stage enum and the valid transition table.

Every project persists exactly one current stage. A transition is only allowed
when the pair is present in the transition table; anything else is rejected
before any side effect happens.
"""

from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    """All pipeline states defined in AGENTS.md."""

    INIT = "INIT"
    BRIEF_READY = "BRIEF_READY"
    CONCEPT_READY = "CONCEPT_READY"
    SCRIPT_READY = "SCRIPT_READY"
    STORYBOARD_READY = "STORYBOARD_READY"
    ASSET_QUERIES_READY = "ASSET_QUERIES_READY"
    ASSETS_DISCOVERED = "ASSETS_DISCOVERED"
    ASSETS_SELECTED = "ASSETS_SELECTED"
    EDIT_BRIEF_READY = "EDIT_BRIEF_READY"
    EDIT_STRATEGY_PROPOSED = "EDIT_STRATEGY_PROPOSED"
    AWAITING_EDIT_STRATEGY_APPROVAL = "AWAITING_EDIT_STRATEGY_APPROVAL"
    EDITING = "EDITING"
    QC = "QC"
    COMPLETE = "COMPLETE"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    CANCELLED = "CANCELLED"


class InvalidTransitionError(Exception):
    """Raised when a pipeline stage transition is not allowed."""

    def __init__(self, from_stage: Stage, to_stage: Stage) -> None:
        self.from_stage = from_stage
        self.to_stage = to_stage
        super().__init__(f"invalid transition: {from_stage.value} -> {to_stage.value}")


# Stages every non-terminal state may move to on failure/cancel.
_FAIL = {Stage.FAILED_RETRYABLE, Stage.FAILED_PERMANENT, Stage.CANCELLED}

TRANSITIONS: dict[Stage, set[Stage]] = {
    Stage.INIT: {Stage.BRIEF_READY, *_FAIL},
    Stage.BRIEF_READY: {Stage.CONCEPT_READY, *_FAIL},
    Stage.CONCEPT_READY: {Stage.SCRIPT_READY, *_FAIL},
    Stage.SCRIPT_READY: {Stage.STORYBOARD_READY, *_FAIL},
    Stage.STORYBOARD_READY: {Stage.ASSET_QUERIES_READY, *_FAIL},
    Stage.ASSET_QUERIES_READY: {Stage.ASSETS_DISCOVERED, *_FAIL},
    Stage.ASSETS_DISCOVERED: {Stage.ASSETS_SELECTED, *_FAIL},
    Stage.ASSETS_SELECTED: {Stage.EDIT_BRIEF_READY, *_FAIL},
    Stage.EDIT_BRIEF_READY: {Stage.EDIT_STRATEGY_PROPOSED, *_FAIL},
    Stage.EDIT_STRATEGY_PROPOSED: {Stage.AWAITING_EDIT_STRATEGY_APPROVAL, *_FAIL},
    Stage.AWAITING_EDIT_STRATEGY_APPROVAL: {Stage.EDITING, *_FAIL},
    Stage.EDITING: {Stage.QC, *_FAIL},
    Stage.QC: {Stage.COMPLETE, *_FAIL},
    Stage.COMPLETE: set(),
    Stage.FAILED_RETRYABLE: {
        Stage.INIT,
        Stage.BRIEF_READY,
        Stage.CONCEPT_READY,
        Stage.SCRIPT_READY,
        Stage.STORYBOARD_READY,
        Stage.ASSET_QUERIES_READY,
        Stage.ASSETS_DISCOVERED,
        Stage.ASSETS_SELECTED,
        Stage.EDIT_BRIEF_READY,
        Stage.EDIT_STRATEGY_PROPOSED,
        Stage.AWAITING_EDIT_STRATEGY_APPROVAL,
        Stage.EDITING,
        Stage.QC,
        Stage.FAILED_PERMANENT,
        Stage.CANCELLED,
    },
    Stage.FAILED_PERMANENT: set(),
    Stage.CANCELLED: set(),
}

TERMINAL_STAGES = {Stage.COMPLETE, Stage.FAILED_PERMANENT, Stage.CANCELLED}
FAILED_STAGES = {Stage.FAILED_RETRYABLE, Stage.FAILED_PERMANENT}


def validate_transition(from_stage: Stage, to_stage: Stage) -> None:
    """Raise InvalidTransitionError if the transition is not allowed."""
    if to_stage not in TRANSITIONS.get(from_stage, set()):
        raise InvalidTransitionError(from_stage, to_stage)


def is_terminal(stage: Stage) -> bool:
    """True for COMPLETE, FAILED_PERMANENT, and CANCELLED."""
    return stage in TERMINAL_STAGES


def is_failed(stage: Stage) -> bool:
    """True for FAILED_RETRYABLE and FAILED_PERMANENT."""
    return stage in FAILED_STAGES


def next_stage_after(stage: Stage) -> Stage | None:
    """The single forward stage after ``stage``, ignoring failure/cancel paths.

    Returns None for terminal stages or when the stage has no unique forward
    successor (FAILED_RETRYABLE resumes to one of several stages, so its caller
    must supply the target explicitly).
    """
    candidates = TRANSITIONS.get(stage, set()) - FAILED_STAGES - {Stage.CANCELLED}
    if len(candidates) == 1:
        return next(iter(candidates))
    return None
