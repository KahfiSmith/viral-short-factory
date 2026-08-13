"""Concept model (docs/03-DATA-CONTRACTS §2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class Concept(BaseModel):
    """The core creative premise of a video."""

    schema_version: str = SCHEMA_VERSION
    project_id: str
    title: str = Field(min_length=1)
    premise: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    comedy_mechanism: str = Field(min_length=1)
    payoff: str = Field(min_length=1)
    stock_footage_feasibility: str = "high"
