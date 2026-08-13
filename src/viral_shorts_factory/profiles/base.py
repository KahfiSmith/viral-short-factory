"""Content profile registry backed by configuration."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from viral_shorts_factory.config.models import AppConfig, ProfileConfig

if TYPE_CHECKING:
    from viral_shorts_factory.domain.script import Script
    from viral_shorts_factory.domain.storyboard import Storyboard

# Map profile name -> deterministic storyboard builder (docs/05 M6). Each module
# in profiles/ that defines build_storyboard_from_script registers here.
StoryboardBuilder = Callable[["Script", ProfileConfig, str], "Storyboard"]
ScriptBuilder = Callable[[str, float], "Script"]
_BUILDERS: dict[str, StoryboardBuilder] = {}
_SCRIPT_BUILDERS: dict[str, ScriptBuilder] = {}


def register_profile(
    name: str,
    builder: StoryboardBuilder,
    script_builder: ScriptBuilder | None = None,
) -> None:
    """Register a profile's storyboard builder (and optional script fixture)."""
    _BUILDERS[name] = builder
    if script_builder is not None:
        _SCRIPT_BUILDERS[name] = script_builder


def get_builder(name: str) -> StoryboardBuilder:
    """Return the storyboard builder for a profile name."""
    try:
        return _BUILDERS[name]
    except KeyError:
        raise ProfileNotFoundError(name, sorted(_BUILDERS)) from None


def get_script_builder(name: str) -> ScriptBuilder | None:
    """Return the profile's script-fixture builder, or None if unregistered."""
    return _SCRIPT_BUILDERS.get(name)


class ProfileNotFoundError(Exception):
    """Raised when a requested content profile is not configured."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(f"unknown profile {name!r}; available: {', '.join(available) or 'none'}")


def get_profile(name: str, config: AppConfig) -> ProfileConfig:
    """Return a profile's config or raise ProfileNotFoundError."""
    profile = config.profiles.get(name)
    if profile is None:
        raise ProfileNotFoundError(name, sorted(config.profiles))
    return profile
