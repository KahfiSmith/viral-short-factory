"""Typer CLI for vsf: doctor, new, inspect."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import typer

# Importing the profile modules runs their register_profile() side effects, so
# vsf plan can resolve builders by name.
import viral_shorts_factory.profiles.facts  # noqa: F401
import viral_shorts_factory.profiles.football_comedy  # noqa: F401
import viral_shorts_factory.profiles.space_mysteries  # noqa: F401
from viral_shorts_factory.cli.assets import assets_app
from viral_shorts_factory.config.loader import ConfigError, load_config
from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.project import ProjectWorkspace, WorkspaceError
from viral_shorts_factory.domain.states import Stage, is_terminal, next_stage_after
from viral_shorts_factory.observability.logging import setup_logging
from viral_shorts_factory.persistence.repositories import DatabaseConnection, ProjectRepository
from viral_shorts_factory.profiles.base import ProfileNotFoundError, get_profile

app = typer.Typer(name="vsf", help="Viral Shorts Factory — short-form video orchestration")
app.add_typer(assets_app)
_log = setup_logging()


def _fail(message: str) -> NoReturn:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=2)


def _resolve_config(config_path: str | None) -> AppConfig:
    try:
        return load_config(Path(config_path) if config_path else None)
    except ConfigError as exc:
        _fail(str(exc))


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _run_version(name: str) -> str | None:
    """Return the first line of `<name> -version` or None on failure."""
    try:
        result = subprocess.run(  # noqa: S603 - name is a fixed literal, not user input
            [name, "-version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    first_line = (result.stdout or result.stderr).splitlines()
    return first_line[0].strip() if first_line else None


def _check(name: str, condition: bool, detail: str = "") -> bool:
    """Print a [PASS]/[FAIL] line and return True on pass."""
    status = "[PASS]" if condition else "[FAIL]"
    suffix = f"  {detail}" if detail else ""
    line = f"{status} {name}{suffix}"
    if condition:
        typer.echo(line)
    else:
        typer.secho(line, fg=typer.colors.RED)
    return condition


@app.command()
def doctor(
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Check the environment: tools, config, project root, and video-use path."""
    any_fail = False

    py_version = sys.version_info
    any_fail |= not _check(
        "Python version",
        py_version >= (3, 11),
        f"{py_version.major}.{py_version.minor}.{py_version.micro}",
    )

    ffmpeg_ok = _command_exists("ffmpeg")
    any_fail |= not _check("ffmpeg", ffmpeg_ok, _run_version("ffmpeg") or "not found")
    ffprobe_ok = _command_exists("ffprobe")
    any_fail |= not _check("ffprobe", ffprobe_ok, _run_version("ffprobe") or "not found")

    try:
        config = _resolve_config(config_path)
    except typer.Exit:
        any_fail = True
        typer.secho("[FAIL] config", fg=typer.colors.RED)
        config = None

    if config is not None:
        project_root = config.app.project_root.expanduser().resolve()
        try:
            project_root.mkdir(parents=True, exist_ok=True)
            test = project_root / ".vsf_write_test"
            test.touch()
            test.unlink()
            writable = True
        except OSError:
            writable = False
        any_fail |= not _check("writable project root", writable, str(project_root))

        repo_path = config.video_use.repo_path.expanduser().resolve()
        repo_ok = repo_path.is_dir()
        skill_ok = (repo_path / "SKILL.md").is_file()
        any_fail |= not _check("video-use path", repo_ok, str(repo_path))
        any_fail |= not _check("video-use SKILL.md", skill_ok, str(repo_path / "SKILL.md"))

        for _provider_name, provider in sorted(config.providers.items()):
            if not provider.enabled or not provider.api_key_env:
                continue
            if not os.environ.get(provider.api_key_env):
                typer.echo(f"[WARN] {provider.api_key_env} missing")

    if any_fail:
        raise typer.Exit(code=1)


@app.command()
def new(
    profile: str = typer.Option(..., "--profile", help="Content profile, e.g. football_comedy"),
    topic: str = typer.Option(..., "--topic", help="Content topic/brief"),
    platform: str | None = typer.Option(None, "--platform", help="Target platform"),
    language: str | None = typer.Option(None, "--language", help="Content language"),
    duration: int | None = typer.Option(None, "--duration", help="Target duration (seconds)"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Create a new project workspace."""
    config = _resolve_config(config_path)
    try:
        profile_config = get_profile(profile, config)
    except ProfileNotFoundError as exc:
        _fail(str(exc))

    if duration is not None:
        min_s = profile_config.min_duration_seconds
        max_s = profile_config.max_duration_seconds
        if not (min_s <= duration <= max_s):
            _fail(f"duration {duration}s outside profile {profile!r} range [{min_s}, {max_s}]")

    workspace = ProjectWorkspace(config)
    try:
        project = workspace.create(
            profile=profile,
            topic=topic,
            platform=platform,
            language=language or profile_config.locale,
            target_duration_seconds=duration,
        )
    except WorkspaceError as exc:
        _fail(str(exc))

    conn = DatabaseConnection(config)
    try:
        ProjectRepository(conn).create(project)
    finally:
        conn.close()

    _log.info(
        "project_created",
        extra={
            "extra_fields": {
                "project_id": project.project_id,
                "profile": profile,
                "topic": topic,
                "workspace": str(workspace.resolve_project_dir(project.project_id)),
            }
        },
    )
    typer.echo(f"created project {project.project_id}")
    typer.echo(f"workspace: {workspace.resolve_project_dir(project.project_id)}")


@app.command()
def inspect(
    project_id: str = typer.Argument(..., help="Project id"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Show details of an existing project workspace."""
    config = _resolve_config(config_path)
    workspace = ProjectWorkspace(config)
    try:
        project, project_dir = workspace.load(project_id)
    except WorkspaceError as exc:
        _fail(str(exc))

    typer.echo(f"Project:      {project.project_id}")
    typer.echo(f"Status:       {project.status.value}")
    typer.echo(f"Profile:      {project.profile}")
    typer.echo(f"Platform:     {project.platform}")
    typer.echo(f"Language:     {project.language}")
    typer.echo(f"Topic:        {project.topic}")
    typer.echo(f"Duration:     {project.target_duration_seconds}s")
    typer.echo(f"Created:      {project.created_at.isoformat()}")
    typer.echo(f"Updated:      {project.updated_at.isoformat()}")
    typer.echo(f"Workspace:    {project_dir}")


@app.command()
def resume(
    project_id: str = typer.Argument(..., help="Project id"),
    approve_edit_strategy: bool = typer.Option(
        False, "--approve-edit-strategy", help="Approve the pending video-use strategy"
    ),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Resume a persisted project: report next stage, or approve the edit strategy."""
    config = _resolve_config(config_path)
    conn = DatabaseConnection(config)
    try:
        project = ProjectRepository(conn).get(project_id)
    finally:
        conn.close()

    if project is None:
        _fail(f"project not found in database: {project_id}")

    if approve_edit_strategy:
        from viral_shorts_factory.editing.video_use_bridge import BridgeError, VideoUseBridge

        bridge = VideoUseBridge(config)
        try:
            proposal = bridge.approve_strategy(project_id, "human")
        except BridgeError as exc:
            _fail(str(exc))
        typer.echo(f"approved strategy {proposal.strategy_id} for {project_id}")
        typer.echo("status: EDITING (render may begin)")
        return

    stage = project.status
    if is_terminal(stage):
        _fail(f"project {project_id} is terminal ({stage.value}); nothing to resume")
    if stage == Stage.FAILED_RETRYABLE:
        typer.echo(f"project {project_id} is FAILED_RETRYABLE; a target stage must be supplied")
        raise typer.Exit(code=1)

    next_stage = next_stage_after(stage)
    typer.echo(f"project {project_id} is at {stage.value}")
    if next_stage is None:
        typer.echo("no single forward stage (caller must choose a target)")
        raise typer.Exit(code=1)
    typer.echo(f"next stage: {next_stage.value}")


@app.command()
def generate(
    topic: str = typer.Option(..., "--topic", help="Content topic"),
    profile: str = typer.Option("facts", "--profile", help="Content profile"),
    script_path: str | None = typer.Option(None, "--script", help="Path to custom script.json"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """All-in-one command: create project, plan queries (8v+4i), & download assets."""
    import json

    from viral_shorts_factory.domain.script import script_from_json, script_to_json
    from viral_shorts_factory.domain.storyboard import storyboard_to_json
    from viral_shorts_factory.pipeline.context import PipelineContext
    from viral_shorts_factory.pipeline.planner import plan_queries
    from viral_shorts_factory.profiles.base import (
        ProfileNotFoundError,
        get_builder,
        get_profile,
        get_script_builder,
    )

    config = _resolve_config(config_path)
    try:
        profile_config = get_profile(profile, config)
    except ProfileNotFoundError as exc:
        _fail(str(exc))

    workspace = ProjectWorkspace(config)
    try:
        project = workspace.create(
            profile=profile,
            topic=topic,
            language=profile_config.locale,
        )
    except WorkspaceError as exc:
        _fail(str(exc))

    conn = DatabaseConnection(config)
    try:
        ProjectRepository(conn).create(project)
    finally:
        conn.close()

    project_id = project.project_id
    project_dir = workspace.resolve_project_dir(project_id)

    # Step 1: Plan queries
    builder = get_builder(profile)
    script_builder = get_script_builder(profile)

    if script_path:
        script_file = Path(script_path).expanduser().resolve()
        if not script_file.is_file():
            _fail(f"script file not found: {script_path}")
        script = script_from_json(script_file.read_text(encoding="utf-8"))
    elif script_builder is not None:
        script = script_builder(topic, float(project.target_duration_seconds))
    else:
        _fail(f"no script found for profile {profile}")

    storyboard = builder(script, profile_config, topic)
    (project_dir / "script.json").write_text(script_to_json(script), encoding="utf-8")
    (project_dir / "storyboard.json").write_text(storyboard_to_json(storyboard), encoding="utf-8")

    ctx = PipelineContext(project=project, config=config, workspace_dir=project_dir)
    queries = plan_queries(storyboard, config, context=ctx)
    (project_dir / "asset_queries.json").write_text(
        json.dumps([q.model_dump(mode="json") for q in queries], indent=2) + "\n",
        encoding="utf-8",
    )

    # Advance state sequentially through the creative chain to ASSET_QUERIES_READY
    conn = DatabaseConnection(config)
    try:
        repo = ProjectRepository(conn)
        creative_chain = [
            Stage.INIT,
            Stage.BRIEF_READY,
            Stage.CONCEPT_READY,
            Stage.SCRIPT_READY,
            Stage.STORYBOARD_READY,
            Stage.ASSET_QUERIES_READY,
        ]
        for idx in range(1, len(creative_chain)):
            repo.update_status(project_id, creative_chain[idx], ctx.run_id)
    finally:
        conn.close()

    # Step 2: Download media assets
    import asyncio

    from viral_shorts_factory.pipeline.runner import run_pipeline

    try:
        proj, pdir, msg = asyncio.run(run_pipeline(project_id, config))
    except Exception as exc:
        _fail(f"asset collection error: {exc}")

    typer.echo(f"[SUCCESS] Collected assets for topic '{topic}'")
    typer.echo(f"Project ID: {project_id}")
    typer.echo(f"Assets saved in: {pdir / 'assets'}")


@app.command()
def plan(
    project_id: str = typer.Argument(..., help="Project id"),
    script_path: str | None = typer.Option(None, "--script", help="Path to a script.json fixture"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Build storyboard + asset queries for a project (Milestone 6 stage).

    Reads script.json from the workspace (or --script), converts beats to a
    storyboard via the profile, validates, writes storyboard.json +
    asset_queries.json, and advances the project state.
    """
    import json

    from viral_shorts_factory.domain.script import ScriptError, script_from_json
    from viral_shorts_factory.domain.storyboard import (
        StoryboardError,
        storyboard_to_json,
        validate_storyboard,
        validate_storyboard_target,
    )
    from viral_shorts_factory.pipeline.context import PipelineContext
    from viral_shorts_factory.pipeline.planner import plan_queries
    from viral_shorts_factory.profiles.base import get_builder, get_profile, get_script_builder

    config = _resolve_config(config_path)
    workspace = ProjectWorkspace(config)
    conn = DatabaseConnection(config)
    try:
        project, project_dir = workspace.load(project_id)
    except WorkspaceError as exc:
        _fail(str(exc))

    profile_config = get_profile(project.profile, config)
    builder = get_builder(project.profile)
    script_builder = get_script_builder(project.profile)

    # Load the script: explicit fixture path, or the workspace script.json,
    # or fall back to the profile's deterministic fixture.
    if script_path:
        script_file = Path(script_path).expanduser().resolve()
    else:
        script_file = project_dir / "script.json"
    if script_file.is_file():
        try:
            script = script_from_json(script_file.read_text(encoding="utf-8"))
        except ScriptError as exc:
            _fail(str(exc))
    elif script_builder is not None:
        script = script_builder(project.topic, float(project.target_duration_seconds))
    else:
        _fail(f"no script found and profile {project.profile!r} has no script fixture")

    storyboard = builder(script, profile_config, project.topic)
    try:
        validate_storyboard(storyboard, profile_config)
        validate_storyboard_target(storyboard, float(script.target_duration_seconds))
    except StoryboardError as exc:
        _fail(str(exc))

    # Persist the script so downstream stages (vsf run) can read it.
    from viral_shorts_factory.domain.script import script_to_json

    (project_dir / "script.json").write_text(script_to_json(script), encoding="utf-8")

    ctx = PipelineContext(project=project, config=config, workspace_dir=project_dir)
    queries = plan_queries(storyboard, config, context=ctx)

    try:
        (project_dir / "storyboard.json").write_text(
            storyboard_to_json(storyboard), encoding="utf-8"
        )
        (project_dir / "asset_queries.json").write_text(
            json.dumps([q.model_dump(mode="json") for q in queries], indent=2) + "\n",
            encoding="utf-8",
        )
        # Persist the state advances along the creative chain up to queries.
        repo = ProjectRepository(conn)
        current = repo.get(project_id)
        if current is None:
            _fail(f"project not found in database: {project_id}")
        # Order of stages from INIT to ASSET_QUERIES_READY.
        creative_chain = [
            Stage.INIT,
            Stage.BRIEF_READY,
            Stage.CONCEPT_READY,
            Stage.SCRIPT_READY,
            Stage.STORYBOARD_READY,
            Stage.ASSET_QUERIES_READY,
        ]
        start_index = (
            creative_chain.index(current.status) if current.status in creative_chain else None
        )
        if start_index is None:
            _fail(f"project {project_id} is at {current.status.value}; cannot plan from this state")
        # Skip the current stage (no-op self-transition is invalid).
        for stage in creative_chain[start_index + 1 :]:
            repo.update_status(project_id, stage, ctx.run_id)

        # Sync project.json (authoritative file per docs/02 §3) with the DB state.
        from viral_shorts_factory.domain.project import _atomic_write

        synced = repo.get(project_id)
        if synced is None:
            raise RuntimeError(f"project vanished during plan: {project_id}")
        _atomic_write(project_dir / "project.json", synced.to_json())
    except Exception as exc:
        _fail(str(exc))
    finally:
        conn.close()

    typer.echo(f"planned {len(storyboard.scenes)} scenes for {project_id}")
    typer.echo(f"  storyboard:     {project_dir / 'storyboard.json'}")
    typer.echo(f"  asset_queries:  {project_dir / 'asset_queries.json'}")
    typer.echo("  status:         ASSET_QUERIES_READY")


def main() -> None:
    """Console-script entry point."""
    app()
