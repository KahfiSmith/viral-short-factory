"""Pipeline runner: orchestrates discovery -> ranking -> download -> brief -> approval gate.

This is the "run" seam that ties the M7-M10 modules together. It executes the
deterministic stages up to the video-use strategy proposal, then STOPS at
AWAITING_EDIT_STRATEGY_APPROVAL (docs/02 §7-8, docs/05 M10) — resuming after
human approval is handled by the caller (vsf resume --approve-edit-strategy).
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from viral_shorts_factory.assets.downloader import DownloadedAsset, Downloader, build_manifest
from viral_shorts_factory.assets.hashing import sha256_file
from viral_shorts_factory.assets.library import AssetLibrary, local_first_search
from viral_shorts_factory.assets.probe import probe_video
from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetCandidate, AssetSearchRequest, MediaType
from viral_shorts_factory.domain.concept import Concept
from viral_shorts_factory.domain.project import Project, ProjectWorkspace
from viral_shorts_factory.domain.script import Script, script_from_json
from viral_shorts_factory.domain.states import Stage
from viral_shorts_factory.domain.storyboard import Storyboard, storyboard_from_json
from viral_shorts_factory.editing.brief import generate_edit_brief, write_edit_brief
from viral_shorts_factory.editing.video_use_bridge import VideoUseBridge
from viral_shorts_factory.persistence.repositories import DatabaseConnection, ProjectRepository
from viral_shorts_factory.pipeline.context import PipelineContext
from viral_shorts_factory.pipeline.planner import plan_queries
from viral_shorts_factory.providers.base import FootageProvider, ProviderError
from viral_shorts_factory.providers.pexels import PexelsProvider
from viral_shorts_factory.providers.pixabay import PixabayProvider
from viral_shorts_factory.providers.unsplash import UnsplashProvider
from viral_shorts_factory.ranking.ranker import select_best_candidates
from viral_shorts_factory.ranking.scoring import CandidateScore

_log = logging.getLogger("vsf.pipeline")


class PipelineError(Exception):
    """Raised when the pipeline cannot continue."""


async def _search_provider(
    provider: FootageProvider, requests: list[AssetSearchRequest]
) -> dict[str, list[AssetCandidate]]:
    """Run provider searches per scene, best-effort (skip provider failures)."""
    found: dict[str, list[AssetCandidate]] = {}
    for request in requests:
        try:
            found.setdefault(request.scene_id, []).extend(await provider.search(request))
        except ProviderError as exc:
            _log.warning(
                "provider search failed for %s (%s): %s", provider.name, request.scene_id, exc
            )
            continue  # provider down / rate-limited: skip, other scenes still proceed
    return found


async def run_pipeline(
    project_id: str,
    config: AppConfig,
    *,
    conn: DatabaseConnection | None = None,
    strategy_text: str | None = None,
) -> tuple[Project, Path, str]:
    """Execute the pipeline up to the edit-strategy approval gate.

    Returns (updated_project, workspace_dir, final_message). Async because the
    provider searches are async.
    """
    workspace = ProjectWorkspace(config)
    project, project_dir = workspace.load(project_id)
    own_conn = conn is None
    conn = conn or DatabaseConnection(config)

    try:
        repo = ProjectRepository(conn)
        current = repo.get(project_id)
        if current is None:
            raise PipelineError(f"project not found in database: {project_id}")
        status = current.status

        # ----- Stage A: ASSET_QUERIES_READY -> discover + rank + download -----
        if status == Stage.ASSET_QUERIES_READY:
            storyboard = _load_storyboard(project_dir)
            script = _load_script(project_dir)
            concept = _load_concept(project_dir, project)

            requests = plan_queries(storyboard, config)
            ctx = PipelineContext(project=current, config=config, workspace_dir=project_dir)

            # 1) Discover: local first, then providers.
            library = AssetLibrary(conn, config)
            by_scene: dict[str, list[AssetCandidate]] = {}
            for request in requests:
                by_scene.setdefault(request.scene_id, []).extend(
                    local_first_search(library, request)
                )

            provider_configs = []
            for name in ("pexels", "pixabay", "unsplash"):
                provider_cfg = config.get_provider(name)
                if provider_cfg is not None:
                    provider_configs.append(name)

            if provider_configs:
                for name in provider_configs:
                    provider: FootageProvider
                    if name == "pexels":
                        try:
                            provider = PexelsProvider.from_config(config)
                        except Exception as exc:  # noqa: BLE001 - key/config issues are non-fatal
                            _log.warning("pexels provider unavailable: %s", exc)
                            continue
                    elif name == "pixabay":
                        try:
                            provider = PixabayProvider.from_config(config, conn)
                        except Exception as exc:  # noqa: BLE001
                            _log.warning("pixabay provider unavailable: %s", exc)
                            continue
                    elif name == "unsplash":
                        try:
                            provider = UnsplashProvider.from_config(config)
                        except Exception as exc:  # noqa: BLE001
                            _log.warning("unsplash provider unavailable: %s", exc)
                            continue
                    else:
                        continue
                    remote = await _search_provider(provider, requests)
                    for scene_id, cands in remote.items():
                        by_scene.setdefault(scene_id, []).extend(cands)

            # 2) Rank per scene.
            ranked = select_best_candidates(by_scene, storyboard, config)

            # 3) Materialize unique candidates per scene (remote bytes are SHA-256 checked).
            downloader = Downloader(config)
            sources_dir = project_dir / "sources"
            assets_dir = project_dir / "assets"
            sources_dir.mkdir(parents=True, exist_ok=True)
            assets_dir.mkdir(parents=True, exist_ok=True)
            selected_assets: dict[str, tuple[AssetCandidate, CandidateScore]] = {}
            selected_media_assets: dict[str, list[tuple[AssetCandidate, CandidateScore, str]]] = {}
            selected_source_paths: dict[str, list[str] | str] = {}
            manifest_items: list[tuple[str, AssetCandidate, DownloadedAsset]] = []
            materialized_by_candidate: dict[str, DownloadedAsset] = {}
            materialized_by_sha256: dict[str, DownloadedAsset] = {}
            selected_candidate_ids: set[str] = set()

            # First reserve one video and one image per scene when available.
            # If the best candidate is byte-identical to an earlier selection,
            # try the next candidate of that media type before reusing it.
            for scene in storyboard.scenes:
                ranked_list = ranked.get(scene.scene_id, [])
                if not ranked_list:
                    continue

                selected_for_scene: list[tuple[AssetCandidate, CandidateScore, str]] = []
                for media_type in (MediaType.VIDEO, MediaType.IMAGE):
                    typed_candidates = [
                        item for item in ranked_list if item[0].media_type == media_type
                    ]
                    fallback: tuple[AssetCandidate, CandidateScore, DownloadedAsset] | None = None
                    for candidate, score in typed_candidates:
                        before_sha256 = set(materialized_by_sha256)
                        try:
                            downloaded_source = _materialize_unique_asset(
                                candidate,
                                scene.scene_id,
                                sources_dir,
                                downloader,
                                library,
                                materialized_by_candidate,
                                materialized_by_sha256,
                            )
                        except Exception as exc:
                            _log.warning(
                                f"failed downloading primary {media_type.value} "
                                f"{candidate.candidate_id}: {exc}"
                            )
                            continue

                        if fallback is None:
                            fallback = (candidate, score, downloaded_source)
                        if downloaded_source.sha256 not in before_sha256:
                            fallback = (candidate, score, downloaded_source)
                            break

                    if fallback is not None:
                        candidate, score, downloaded_source = fallback
                        selected_for_scene.append(
                            (
                                candidate,
                                score,
                                _project_relative_path(downloaded_source.local_path, project_dir),
                            )
                        )
                        selected_candidate_ids.add(candidate.candidate_id)
                        manifest_items.append((scene.scene_id, candidate, downloaded_source))

                if selected_for_scene:
                    selected_media_assets[scene.scene_id] = selected_for_scene
                    selected_source_paths[scene.scene_id] = [item[2] for item in selected_for_scene]
                    primary = next(
                        (
                            item
                            for item in selected_for_scene
                            if item[0].media_type == MediaType.VIDEO
                        ),
                        selected_for_scene[0],
                    )
                    selected_assets[scene.scene_id] = (primary[0], primary[1])

            # Then materialize remaining ranked alternatives. Primary sources
            # are skipped because they already have canonical files in sources/.
            for scene in storyboard.scenes:
                for cand, _ in ranked.get(scene.scene_id, [])[1:]:
                    if cand.candidate_id in selected_candidate_ids:
                        continue
                    try:
                        _materialize_unique_asset(
                            cand,
                            scene.scene_id,
                            assets_dir,
                            downloader,
                            library,
                            materialized_by_candidate,
                            materialized_by_sha256,
                        )
                    except Exception as exc:
                        _log.warning(f"failed downloading asset {cand.candidate_id}: {exc}")

            # 4) Persist: manifest, edit brief, state advances.
            manifest = build_manifest(project.project_id, manifest_items)
            (project_dir / "source_manifest.json").write_text(manifest.to_json(), encoding="utf-8")
            brief = generate_edit_brief(
                project,
                concept,
                script,
                storyboard,
                selected_assets,
                config,
                selected_source_paths=selected_source_paths,
                selected_media_assets=selected_media_assets,
            )
            write_edit_brief(brief, project_dir / "edit_brief.md")

            chain = [
                Stage.ASSETS_DISCOVERED,
                Stage.ASSETS_SELECTED,
                Stage.EDIT_BRIEF_READY,
                Stage.EDIT_STRATEGY_PROPOSED,
            ]
            for stage in chain:
                repo.update_status(project_id, stage, ctx.run_id)
            _sync_project_json(project_dir, repo, project_id)

            project, project_dir = workspace.load(project_id)
            status = Stage.EDIT_STRATEGY_PROPOSED

        # ----- Stage B: propose strategy (write proposal) if not yet done -----
        if status == Stage.EDIT_STRATEGY_PROPOSED:
            bridge = VideoUseBridge(config)
            bridge.propose_strategy(
                project_id, strategy_text or "Standard fast-cut edit with punchline emphasis."
            )
            project, project_dir = workspace.load(project_id)

        if status not in (Stage.AWAITING_EDIT_STRATEGY_APPROVAL, Stage.EDIT_STRATEGY_PROPOSED):
            raise PipelineError(f"pipeline cannot run from state {status.value}")

        return project, project_dir, "awaiting edit strategy approval"
    finally:
        if own_conn:
            conn.close()


def _project_relative_path(path: str, project_dir: Path) -> str:
    """Return a manifest/edit-brief path relative to the project workspace."""
    candidate_path = Path(path)
    try:
        return candidate_path.relative_to(project_dir).as_posix()
    except ValueError:
        return str(candidate_path)


def _materialize_unique_asset(
    candidate: AssetCandidate,
    scene_id: str,
    destination_dir: Path,
    downloader: Downloader,
    library: AssetLibrary,
    by_candidate: dict[str, DownloadedAsset],
    by_sha256: dict[str, DownloadedAsset],
) -> DownloadedAsset:
    """Materialize once per candidate and once per file checksum per run.

    Provider IDs are not a safe cross-provider identity. The downloaded bytes
    are therefore hashed before deciding whether a newly materialized file is
    a duplicate. The first path remains canonical; later duplicate files are
    removed and the canonical record is reused.
    """
    cached = by_candidate.get(candidate.candidate_id)
    if cached is not None:
        return cached

    downloaded = _materialize_asset(candidate, scene_id, destination_dir, downloader, library)
    by_candidate[candidate.candidate_id] = downloaded

    canonical = by_sha256.get(downloaded.sha256)
    if canonical is not None:
        duplicate_path = Path(downloaded.local_path)
        canonical_path = Path(canonical.local_path)
        if duplicate_path != canonical_path:
            duplicate_path.unlink(missing_ok=True)
        return canonical

    by_sha256[downloaded.sha256] = downloaded
    return downloaded


def _materialize_asset(
    candidate: AssetCandidate,
    scene_id: str,
    sources_dir: Path,
    downloader: Downloader,
    library: AssetLibrary,
) -> DownloadedAsset:
    """Download a remote candidate, or copy a local library file into sources/.

    Local candidates carry no download URL; their file lives in the library and
    is referenced by provider_asset_id == library asset_id.
    """
    if candidate.provider != "local":
        return downloader.download_candidate(candidate, scene_id, sources_dir)

    entry = library.get(candidate.provider_asset_id)
    if entry is None:
        raise PipelineError(f"local candidate {candidate.candidate_id} not found in library")
    source = Path(entry.local_path)
    if not source.is_file():
        raise PipelineError(f"local asset file missing: {source}")

    target = sources_dir / f"{scene_id}_{candidate.provider}_{candidate.provider_asset_id}.mp4"
    shutil.copy2(source, target)
    probe = probe_video(target)
    return DownloadedAsset(
        asset_id=entry.asset_id,
        candidate_id=candidate.candidate_id,
        local_path=str(target),
        sha256=sha256_file(target),
        bytes=target.stat().st_size,
        probe=probe,
    )


def _sync_project_json(project_dir: Path, repo: ProjectRepository, project_id: str) -> None:
    from viral_shorts_factory.domain.project import _atomic_write

    synced = repo.get(project_id)
    if synced is None:
        raise PipelineError(f"project vanished during run: {project_id}")
    _atomic_write(project_dir / "project.json", synced.to_json())


def _load_storyboard(project_dir: Path) -> Storyboard:
    path = project_dir / "storyboard.json"
    if not path.is_file():
        raise PipelineError(f"storyboard.json missing in {project_dir}")
    return storyboard_from_json(path.read_text(encoding="utf-8"))


def _load_script(project_dir: Path) -> Script:
    path = project_dir / "script.json"
    if not path.is_file():
        raise PipelineError(f"script.json missing in {project_dir}")
    return script_from_json(path.read_text(encoding="utf-8"))


def _load_concept(project_dir: Path, project: Project) -> Concept:
    path = project_dir / "concept.json"
    if path.is_file():
        return Concept.model_validate(json.loads(path.read_text(encoding="utf-8")))
    # Fallback concept derived from the project topic.
    return Concept(
        project_id=project.project_id,
        title=project.topic,
        premise=f"Short comedy about {project.topic}.",
        hook=f"Watch what happens with {project.topic}.",
        comedy_mechanism="expectation_vs_reality",
        payoff="The confidence exceeds the ability.",
    )
