"""CLI tests via Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from viral_shorts_factory.cli.app import app
from viral_shorts_factory.config.loader import load_config
from viral_shorts_factory.domain.project import ProjectWorkspace
from viral_shorts_factory.domain.states import Stage
from viral_shorts_factory.persistence.repositories import DatabaseConnection, ProjectRepository

runner = CliRunner()


@pytest.fixture()
def config_yaml(tmp_path: Path) -> Path:
    """A minimal config pointing at tmp_path, with a fake video-use repo."""
    video_use = tmp_path / "video-use"
    video_use.mkdir()
    (video_use / "SKILL.md").write_text("# video-use\n", encoding="utf-8")
    raw = {
        "app": {
            "project_root": str(tmp_path / "projects"),
            "asset_library_root": str(tmp_path / "assets"),
            "database_path": str(tmp_path / "vsf.sqlite3"),
        },
        "video_use": {"repo_path": str(video_use), "require_strategy_approval": True},
        "defaults": {"platform": "youtube_shorts", "language": "id-ID"},
        "providers": {
            "local": {"enabled": True, "priority": 10},
            "pexels": {"enabled": True, "priority": 20, "api_key_env": "PEXELS_API_KEY"},
            "pixabay": {"enabled": True, "priority": 30, "api_key_env": "PIXABAY_API_KEY"},
        },
        "downloads": {
            "max_candidates_per_scene": 2,
            "max_file_size_mb": 250,
            "timeout_seconds": 60,
        },
        "ranking": {
            "weights": {
                "query_match": 0.30,
                "orientation": 0.25,
                "resolution": 0.15,
                "duration_fit": 0.15,
                "source_confidence": 0.10,
                "duplicate_penalty": 0.05,
            }
        },
        "profiles": {
            "football_comedy": {
                "min_duration_seconds": 18,
                "max_duration_seconds": 35,
                "locale": "id-ID",
            }
        },
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_doctor_passes(config_yaml: Path) -> None:
    result = runner.invoke(app, ["doctor", "--config", str(config_yaml)])
    assert result.exit_code == 0, result.output
    assert "[PASS] ffmpeg" in result.output
    assert "[PASS] ffprobe" in result.output
    assert "[PASS] writable project root" in result.output
    assert "[PASS] video-use path" in result.output
    assert "[PASS] video-use SKILL.md" in result.output


def test_doctor_fails_on_bad_config(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [valid\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--config", str(bad)])
    assert result.exit_code == 1
    assert "[FAIL] config" in result.output


def test_new_creates_workspace(config_yaml: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--profile",
            "football_comedy",
            "--topic",
            "kiper tarkam",
            "--config",
            str(config_yaml),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "created project" in result.output
    assert "workspace:" in result.output


def test_new_rejects_unknown_profile(config_yaml: Path) -> None:
    result = runner.invoke(
        app,
        ["new", "--profile", "bogus", "--topic", "x", "--config", str(config_yaml)],
    )
    assert result.exit_code == 2
    assert "unknown profile" in result.output


def test_new_rejects_out_of_range_duration(config_yaml: Path) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "--profile",
            "football_comedy",
            "--topic",
            "x",
            "--duration",
            "100",
            "--config",
            str(config_yaml),
        ],
    )
    assert result.exit_code == 2
    assert "outside profile" in result.output


def test_new_persists_to_sqlite(config_yaml: Path) -> None:
    import yaml as _yaml

    raw = _yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    db_path = Path(raw["app"]["database_path"])

    result = runner.invoke(
        app,
        [
            "new",
            "--profile",
            "football_comedy",
            "--topic",
            "db row",
            "--config",
            str(config_yaml),
        ],
    )
    assert result.exit_code == 0, result.output
    assert db_path.is_file()

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT project_id, status FROM projects").fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][1] == "INIT"


def test_resume_reports_next_stage(config_yaml: Path) -> None:
    new_result = runner.invoke(
        app,
        [
            "new",
            "--profile",
            "football_comedy",
            "--topic",
            "resume me",
            "--config",
            str(config_yaml),
        ],
    )
    assert new_result.exit_code == 0
    project_id = next(
        line.split()[2] for line in new_result.output.splitlines() if line.startswith("created")
    )

    # Advance the project through the pipeline to ASSETS_SELECTED (simulated interrupted run).
    config = load_config(config_yaml)
    conn = DatabaseConnection(config)
    try:
        repo = ProjectRepository(conn)
        chain = [
            Stage.BRIEF_READY,
            Stage.CONCEPT_READY,
            Stage.SCRIPT_READY,
            Stage.STORYBOARD_READY,
            Stage.ASSET_QUERIES_READY,
            Stage.ASSETS_DISCOVERED,
            Stage.ASSETS_SELECTED,
        ]
        for stage in chain:
            repo.update_status(project_id, stage, "run_1")
    finally:
        conn.close()

    result = runner.invoke(app, ["resume", project_id, "--config", str(config_yaml)])
    assert result.exit_code == 0, result.output
    assert f"project {project_id} is at ASSETS_SELECTED" in result.output
    assert "next stage: EDIT_BRIEF_READY" in result.output


def test_resume_missing_project(config_yaml: Path) -> None:
    result = runner.invoke(app, ["resume", "20260812-nope-00000000", "--config", str(config_yaml)])
    assert result.exit_code == 2
    assert "not found in database" in result.output


def test_assets_register_list_search_inspect(config_yaml: Path, video_fixture: Path) -> None:
    register = runner.invoke(
        app,
        [
            "assets",
            "register",
            str(video_fixture),
            "--category",
            "football",
            "--tag",
            "goal",
            "--tag",
            "portrait",
            "--rights",
            "PROVIDER_LICENSED",
            "--config",
            str(config_yaml),
        ],
    )
    assert register.exit_code == 0, register.output
    assert "registered asset_" in register.output
    asset_id = register.output.split()[1]

    listing = runner.invoke(app, ["assets", "list", "--config", str(config_yaml)])
    assert listing.exit_code == 0
    assert asset_id in listing.output
    assert "PROVIDER_LICENSED" in listing.output

    search = runner.invoke(app, ["assets", "search", "goal", "--config", str(config_yaml)])
    assert search.exit_code == 0
    assert asset_id in search.output

    inspect = runner.invoke(app, ["assets", "inspect", asset_id, "--config", str(config_yaml)])
    assert inspect.exit_code == 0
    assert f"asset_id:      {asset_id}" in inspect.output
    assert "1080x1920" in inspect.output


def test_assets_register_missing_file(config_yaml: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["assets", "register", str(tmp_path / "nope.mp4"), "--config", str(config_yaml)],
    )
    assert result.exit_code == 2
    assert "not a file" in result.output


def test_assets_inspect_missing(config_yaml: Path) -> None:
    result = runner.invoke(app, ["assets", "inspect", "asset_nope", "--config", str(config_yaml)])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_plan_builds_storyboard_and_queries(config_yaml: Path) -> None:
    # Create a project via CLI.
    new_result = runner.invoke(
        app,
        ["new", "--profile", "football_comedy", "--topic", "plan me", "--config", str(config_yaml)],
    )
    assert new_result.exit_code == 0, new_result.output
    project_id = next(
        line.split()[2] for line in new_result.output.splitlines() if line.startswith("created")
    )

    # Project starts INIT; plan advances through the creative chain.
    result = runner.invoke(app, ["plan", project_id, "--config", str(config_yaml)])
    assert result.exit_code == 0, result.output
    assert f"planned 4 scenes for {project_id}" in result.output
    assert "status:         ASSET_QUERIES_READY" in result.output

    # Verify workspace artifacts + DB status.
    config = load_config(config_yaml)
    workspace = ProjectWorkspace(config)
    _project, project_dir = workspace.load(project_id)
    assert (project_dir / "storyboard.json").is_file()
    assert (project_dir / "asset_queries.json").is_file()

    conn = DatabaseConnection(config)
    try:
        loaded = ProjectRepository(conn).get(project_id)
    finally:
        conn.close()
    assert loaded is not None
    assert loaded.status == Stage.ASSET_QUERIES_READY

    # project.json (authoritative file) must be synced to the same status.
    import json as _json

    raw = _json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert raw["status"] == "ASSET_QUERIES_READY"


def test_plan_with_custom_script(config_yaml: Path, tmp_path: Path) -> None:
    from viral_shorts_factory.domain.script import Beat, BeatType, Script

    new_result = runner.invoke(
        app,
        ["new", "--profile", "football_comedy", "--topic", "custom", "--config", str(config_yaml)],
    )
    assert new_result.exit_code == 0
    project_id = next(
        line.split()[2] for line in new_result.output.splitlines() if line.startswith("created")
    )

    script = Script(
        schema_version="1.0",
        target_duration_seconds=28.0,
        beats=[
            Beat(id="x1", type=BeatType.HOOK, text="A.", estimated_seconds=10.0),
            Beat(id="x2", type=BeatType.PAYOFF, text="B.", estimated_seconds=18.0),
        ],
    )
    script_file = tmp_path / "script.json"
    script_file.write_text(script.model_dump_json(indent=2), encoding="utf-8")

    result = runner.invoke(
        app, ["plan", project_id, "--script", str(script_file), "--config", str(config_yaml)]
    )
    assert result.exit_code == 0, result.output
    assert "planned 2 scenes" in result.output


def test_inspect_roundtrip(config_yaml: Path) -> None:
    new_result = runner.invoke(
        app,
        [
            "new",
            "--profile",
            "football_comedy",
            "--topic",
            "kiper tarkam",
            "--config",
            str(config_yaml),
        ],
    )
    assert new_result.exit_code == 0
    project_id = next(
        line.split()[2] for line in new_result.output.splitlines() if line.startswith("created")
    )

    inspect_result = runner.invoke(app, ["inspect", project_id, "--config", str(config_yaml)])
    assert inspect_result.exit_code == 0, inspect_result.output
    assert f"Project:      {project_id}" in inspect_result.output
    assert "Status:       INIT" in inspect_result.output
    assert "Profile:      football_comedy" in inspect_result.output


def test_inspect_missing_project(config_yaml: Path) -> None:
    result = runner.invoke(app, ["inspect", "20260812-nope-00000000", "--config", str(config_yaml)])
    assert result.exit_code == 2
    assert "not found" in result.output
