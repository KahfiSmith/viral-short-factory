"""vsf assets subcommand group (docs/08-OPERATIONS §4)."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from viral_shorts_factory.assets.library import AssetLibrary, AssetLibraryError
from viral_shorts_factory.config.loader import ConfigError, load_config
from viral_shorts_factory.domain.assets import RightsStatus
from viral_shorts_factory.persistence.repositories import DatabaseConnection

assets_app = typer.Typer(name="assets", help="Manage the local asset library", no_args_is_help=True)


def _library(config_path: str | None) -> tuple[AssetLibrary, DatabaseConnection]:
    try:
        config = load_config(Path(config_path) if config_path else None)
    except ConfigError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    conn = DatabaseConnection(config)
    return AssetLibrary(conn, config), conn


def _fail(message: str) -> NoReturn:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=2)


def _rights_option(value: str | None) -> RightsStatus | None:
    if value is None:
        return None
    try:
        return RightsStatus(value)
    except ValueError:
        _fail(f"invalid rights status {value!r}; choose from {[s.value for s in RightsStatus]}")


@assets_app.command("register")
def register(
    path: str = typer.Argument(..., help="Path to a local video file"),
    category: str | None = typer.Option(None, "--category", help="Asset category"),
    tag: list[str] = typer.Option([], "--tag", help="Tag (repeatable)"),
    provider: str | None = typer.Option(None, "--provider", help="Source provider"),
    provider_asset_id: str | None = typer.Option(
        None, "--provider-asset-id", help="Provider asset id"
    ),
    source_url: str | None = typer.Option(None, "--source-url", help="Source page URL"),
    rights: str | None = typer.Option(
        None, "--rights", help=f"Rights status ({', '.join(s.value for s in RightsStatus)})"
    ),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Register a local video file into the asset library."""
    library, conn = _library(config_path)
    try:
        entry = library.register(
            Path(path),
            category=category,
            tags=tag,
            provider=provider,
            provider_asset_id=provider_asset_id,
            source_page_url=source_url,
            rights_status=_rights_option(rights) or RightsStatus.UNVERIFIED,
        )
    except AssetLibraryError as exc:
        _fail(str(exc))
    finally:
        conn.close()

    typer.echo(f"registered {entry.asset_id} ({entry.sha256[:16]}...)")
    typer.echo(f"  path:    {entry.local_path}")
    typer.echo(f"  rights:  {entry.rights_status}")
    typer.echo(f"  size:    {entry.width}x{entry.height} {entry.orientation}")
    typer.echo(f"  duration:{entry.duration_seconds:.1f}s")


@assets_app.command("list")
def list_assets(
    category: str | None = typer.Option(None, "--category", help="Filter by category"),
    tag: list[str] = typer.Option([], "--tag", help="Filter by tag (repeatable)"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """List assets in the local library."""
    library, conn = _library(config_path)
    try:
        entries = library.search(category=category, tags=tag or None)
    finally:
        conn.close()

    if not entries:
        typer.echo("no assets in library")
        return
    for entry in entries:
        dur = f"{entry.duration_seconds:.1f}s" if entry.duration_seconds is not None else "-"
        size = f"{entry.width}x{entry.height}" if entry.width else "-"
        typer.echo(
            f"{entry.asset_id}  {entry.rights_status:<18} {size:>9} {dur:>7} "
            f"uses={entry.use_count}  {Path(entry.local_path).name}"
        )


@assets_app.command("inspect")
def inspect_asset(
    asset_id: str = typer.Argument(..., help="Asset id"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Show full metadata for a library asset."""
    library, conn = _library(config_path)
    try:
        entry = library.get(asset_id)
    finally:
        conn.close()
    if entry is None:
        _fail(f"asset not found: {asset_id}")

    typer.echo(f"asset_id:      {entry.asset_id}")
    typer.echo(f"sha256:        {entry.sha256}")
    typer.echo(f"path:          {entry.local_path}")
    typer.echo(f"rights:        {entry.rights_status}")
    typer.echo(f"category:      {entry.category or '-'}")
    typer.echo(f"tags:          {', '.join(entry.tags) or '-'}")
    typer.echo(f"size:          {entry.width}x{entry.height} ({entry.orientation})")
    typer.echo(
        f"duration:      {entry.duration_seconds:.1f}s"
        if entry.duration_seconds
        else "duration:      -"
    )
    typer.echo(f"provider:      {entry.provider or '-'}")
    typer.echo(f"provider_id:   {entry.provider_asset_id or '-'}")
    typer.echo(f"source_url:    {entry.source_page_url or '-'}")
    typer.echo(f"created:       {entry.created_at.isoformat()}")
    typer.echo(f"last_used:     {entry.last_used_at.isoformat() if entry.last_used_at else '-'}")
    typer.echo(f"use_count:     {entry.use_count}")


@assets_app.command("search")
def search_assets(
    query: str = typer.Argument(..., help="Tag/query to search"),
    category: str | None = typer.Option(None, "--category", help="Filter by category"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Search the local library by tag (and optional category)."""
    library, conn = _library(config_path)
    try:
        entries = library.search(category=category, tags=[query])
    finally:
        conn.close()

    if not entries:
        typer.echo("no matching assets")
        return
    for entry in entries:
        typer.echo(
            f"{entry.asset_id}  {entry.rights_status:<18} "
            f"{entry.width}x{entry.height}  {Path(entry.local_path).name}"
        )
