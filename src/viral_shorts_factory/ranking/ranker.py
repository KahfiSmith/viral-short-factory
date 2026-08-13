"""Candidate ranker engine (docs/03 §7, docs/05 M7)."""

from __future__ import annotations

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetCandidate, RightsStatus
from viral_shorts_factory.domain.storyboard import Scene, Storyboard
from viral_shorts_factory.ranking.scoring import CandidateScore, score_candidate


def rank_candidates(
    candidates: list[AssetCandidate],
    scene: Scene,
    config: AppConfig,
    *,
    already_used_ids: set[str] | None = None,
) -> list[tuple[AssetCandidate, CandidateScore]]:
    """Rank a list of candidates for a scene deterministically.

    Filters out UNVERIFIED and REJECTED candidates per docs/07 §4.
    Returns list of (candidate, score) tuples sorted descending by score total,
    then by candidate_id for stable deterministic sorting.
    """
    weights = config.ranking.weights
    used_ids = already_used_ids or set()

    scored: list[tuple[AssetCandidate, CandidateScore]] = []
    for cand in candidates:
        if cand.rights_status in (RightsStatus.UNVERIFIED, RightsStatus.REJECTED):
            continue
        sc = score_candidate(cand, scene, weights, already_used_ids=used_ids)
        if sc.total > 0.0:
            scored.append((cand, sc))

    # Stable deterministic sort
    scored.sort(key=lambda item: (-item[1].total, item[0].candidate_id))
    return scored


def select_best_candidates(
    candidates_by_scene: dict[str, list[AssetCandidate]],
    storyboard: Storyboard,
    config: AppConfig,
) -> dict[str, list[tuple[AssetCandidate, CandidateScore]]]:
    """Select ranked candidates per scene across the whole storyboard.

    Tracks already-selected candidates across scenes to penalize duplicates.
    Returns scene_id -> list of (AssetCandidate, CandidateScore).
    """
    results: dict[str, list[tuple[AssetCandidate, CandidateScore]]] = {}
    already_used: set[str] = set()

    for scene in storyboard.scenes:
        cands = candidates_by_scene.get(scene.scene_id, [])
        ranked = rank_candidates(cands, scene, config, already_used_ids=already_used)
        results[scene.scene_id] = ranked

        # Record top choice into already_used to penalize reuse in later scenes
        if ranked:
            top_cand = ranked[0][0]
            already_used.add(top_cand.candidate_id)
            already_used.add(top_cand.provider_asset_id)

    return results
