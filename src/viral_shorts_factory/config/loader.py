"""Load and validate the application configuration from YAML."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from viral_shorts_factory.config.models import AppConfig

# Path to the repo-root examples/config.example.yaml when running from a source
# checkout. Resolves src/viral_shorts_factory/config/loader.py -> repo root.
_DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "examples" / "config.example.yaml"
_DEFAULT_DOTENV = Path(__file__).resolve().parents[3] / ".env"

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or is invalid."""


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ.

    Does not override variables already set in the environment. Lines are
    trimmed; blank lines and lines starting with '#' are ignored. Values may be
    quoted with single or double quotes.
    """
    dotenv = (path or _DEFAULT_DOTENV).expanduser().resolve()
    if not dotenv.is_file():
        return
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _expand_string(value: str) -> str:
    """Expand leading ~ and ${ENV_VAR} references in a string field."""
    expanded = _ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), value)
    return os.path.expanduser(expanded)


def _expand_value(value: object) -> object:
    if isinstance(value, str):
        return _expand_string(value)
    if isinstance(value, list):
        return [_expand_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_value(item) for key, item in value.items()}
    return value


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from a YAML file.

    Defaults to the repo's examples/config.example.yaml. Loads the repo-root
    .env file into the environment first (without overriding already-exported
    vars), then expands `~` and `${ENV_VAR}` references in string fields before
    validation. Secret values are never read here — config only references them
    by environment variable name.
    """
    load_dotenv()
    config_path = (path or _DEFAULT_CONFIG).expanduser().resolve()
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"config path is not a file: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - pyyaml error surfaces
        raise ConfigError(f"invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"config root must be a mapping, got {type(raw).__name__}")

    try:
        return AppConfig.model_validate(_expand_value(raw))
    except Exception as exc:
        raise ConfigError(f"invalid configuration in {config_path}: {exc}") from exc
