"""Script model (docs/03-DATA-CONTRACTS §3)."""

from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class BeatType(StrEnum):
    """Allowed script beat types (docs/03 §3)."""

    HOOK = "hook"
    SETUP = "setup"
    ESCALATION = "escalation"
    PAYOFF = "payoff"
    REACTION = "reaction"
    CTA = "cta"


class ScriptError(Exception):
    """Raised when a script is invalid."""


class Beat(BaseModel):
    """A single script beat."""

    id: str = Field(min_length=1)
    type: BeatType
    text: str = Field(min_length=1)
    estimated_seconds: float = Field(ge=1.0)


class Script(BaseModel):
    """A timed, beat-structured script."""

    schema_version: str = SCHEMA_VERSION
    target_duration_seconds: float = Field(ge=1.0)
    beats: list[Beat] = Field(min_length=1)


def validate_script(script: Script) -> None:
    """Validate a script; raises ScriptError on problems."""
    if not script.beats:
        raise ScriptError("script must have at least one beat")
    ids = [b.id for b in script.beats]
    if len(ids) != len(set(ids)):
        raise ScriptError("script beat ids must be unique")
    total = sum(b.estimated_seconds for b in script.beats)
    if total <= 0:
        raise ScriptError("script beats must have positive total duration")


def script_to_json(script: Script) -> str:
    return script.model_dump_json(indent=2) + "\n"


def script_from_json(text: str) -> Script:
    try:
        script = Script.model_validate(json.loads(text))
    except Exception as exc:
        raise ScriptError(f"invalid script: {exc}") from exc
    validate_script(script)
    return script


def script_to_dict(script: Script) -> dict[str, object]:
    return script.model_dump(mode="json")
