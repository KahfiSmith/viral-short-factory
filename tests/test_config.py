"""Config loading and validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from viral_shorts_factory.config.loader import ConfigError, load_config
from viral_shorts_factory.config.models import AppConfig


def test_example_config_loads(example_config_path: Path) -> None:
    config = load_config(example_config_path)
    assert isinstance(config, AppConfig)
    assert config.video_use.require_strategy_approval is True
    assert config.defaults.aspect_ratio == "9:16"
    assert config.profiles["football_comedy"].min_duration_seconds == 18
    assert config.profiles["football_comedy"].max_duration_seconds == 35


def test_missing_config_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(bad)


def test_inverted_profile_bounds_rejected(tmp_path: Path) -> None:
    raw = _base_raw(tmp_path)
    raw["profiles"]["football_comedy"] = {"min_duration_seconds": 40, "max_duration_seconds": 20}
    path = tmp_path / "bad_profile.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match="min_duration_seconds must be <= max_duration_seconds"):
        load_config(path)


def test_duplicate_provider_priorities_rejected(tmp_path: Path) -> None:
    raw = _base_raw(tmp_path)
    raw["providers"]["pexels"]["priority"] = 10  # same as local
    path = tmp_path / "dup_priority.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match="unique priorities"):
        load_config(path)


def test_ranking_weights_must_sum_to_one(tmp_path: Path) -> None:
    raw = _base_raw(tmp_path)
    raw["ranking"]["weights"]["query_match"] = 0.9
    path = tmp_path / "bad_weights.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ConfigError, match="must sum to 1.0"):
        load_config(path)


def test_env_var_expansion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    expanded_root = tmp_path / "expanded"
    monkeypatch.setenv("VSF_TEST_ROOT", str(expanded_root))
    raw = _base_raw(tmp_path)
    raw["app"]["project_root"] = "${VSF_TEST_ROOT}/projects"
    path = tmp_path / "env_expand.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config = load_config(path)
    assert str(config.app.project_root) == str(expanded_root / "projects")


def test_secrets_referenced_by_name_only(tmp_path: Path) -> None:
    """Config must not contain secret values, only env-var names."""
    raw = _base_raw(tmp_path)
    dumped = yaml.safe_dump(raw)
    assert "sk_" not in dumped
    assert "api_key" not in dumped.lower() or "api_key_env" in dumped


def _base_raw(tmp_path: Path) -> dict:
    raw = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "examples" / "config.example.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(raw, dict)
    raw["app"] = {
        "project_root": str(tmp_path / "projects"),
        "asset_library_root": str(tmp_path / "assets"),
        "database_path": str(tmp_path / "vsf.sqlite3"),
    }
    raw["video_use"] = {"repo_path": str(tmp_path / "video-use")}
    return raw
