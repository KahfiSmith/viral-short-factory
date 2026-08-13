"""Candidate scoring and ranking models & algorithms (docs/03 §7, docs/05 M7)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from viral_shorts_factory.config.models import RankingWeights
from viral_shorts_factory.domain.assets import AssetCandidate, RightsStatus
from viral_shorts_factory.domain.storyboard import Scene


class ScoreComponents(BaseModel):
    """Component scores for a candidate (0.0 - 1.0 each)."""

    query_match: float = Field(ge=0.0, le=1.0)
    orientation: float = Field(ge=0.0, le=1.0)
    resolution: float = Field(ge=0.0, le=1.0)
    duration_fit: float = Field(ge=0.0, le=1.0)
    source_confidence: float = Field(ge=0.0, le=1.0)
    duplicate_penalty: float = Field(ge=0.0, le=1.0)


class CandidateScore(BaseModel):
    """Scored candidate entry (docs/03-DATA-CONTRACTS §7)."""

    candidate_id: str
    scene_id: str
    total: float = Field(ge=0.0, le=1.0)
    components: ScoreComponents
    ranker_version: str = "rules-v1"


def score_candidate(
    candidate: AssetCandidate,
    scene: Scene,
    weights: RankingWeights,
    *,
    already_used_ids: set[str] | None = None,
) -> CandidateScore:
    """Calculate deterministic v1 score for an asset candidate against a scene.

    Rights status UNVERIFIED or REJECTED results in total score = 0.0.
    """
    already_used = already_used_ids or set()

    # Provenance / Rights gate check
    if candidate.rights_status in (RightsStatus.UNVERIFIED, RightsStatus.REJECTED):
        components = ScoreComponents(
            query_match=0.0,
            orientation=0.0,
            resolution=0.0,
            duration_fit=0.0,
            source_confidence=0.0,
            duplicate_penalty=1.0 if candidate.candidate_id in already_used else 0.0,
        )
        return CandidateScore(
            candidate_id=candidate.candidate_id,
            scene_id=scene.scene_id,
            total=0.0,
            components=components,
        )

    # 1. Query match (simplest token overlap ratio)
    q_match = _score_query_match(candidate, scene)

    # 2. Orientation fit
    orient = _score_orientation(candidate, scene)

    # 3. Resolution fit
    res = _score_resolution(candidate, scene)

    # 4. Duration fit
    dur = _score_duration(candidate, scene)

    # 5. Source confidence
    source_conf = _score_source_confidence(candidate)

    # 6. Duplicate / already-used penalty
    is_dup = candidate.candidate_id in already_used or candidate.provider_asset_id in already_used
    dup_pen = 1.0 if is_dup else 0.0

    # Weighted total calculation
    # Weights sum to 1.0. duplicate_penalty reduces score if present.
    base_score = (
        q_match * weights.query_match
        + orient * weights.orientation
        + res * weights.resolution
        + dur * weights.duration_fit
        + source_conf * weights.source_confidence
    )
    # Apply penalty factor (reducing by weight * penalty)
    total = max(0.0, min(1.0, base_score - (dup_pen * weights.duplicate_penalty)))

    components = ScoreComponents(
        query_match=round(q_match, 4),
        orientation=round(orient, 4),
        resolution=round(res, 4),
        duration_fit=round(dur, 4),
        source_confidence=round(source_conf, 4),
        duplicate_penalty=round(dup_pen, 4),
    )

    return CandidateScore(
        candidate_id=candidate.candidate_id,
        scene_id=scene.scene_id,
        total=round(total, 4),
        components=components,
    )


def _score_query_match(candidate: AssetCandidate, scene: Scene) -> float:
    cand_tokens = set(candidate.query.lower().split())
    for tag in candidate.tags:
        cand_tokens.update(tag.lower().split())

    best_match = 0.0
    for scene_q in scene.queries:
        scene_tokens = set(scene_q.lower().split())
        if not scene_tokens:
            continue
        overlap = len(cand_tokens & scene_tokens)
        ratio = overlap / len(scene_tokens)
        if ratio > best_match:
            best_match = ratio

    return min(1.0, best_match)


def _score_orientation(candidate: AssetCandidate, scene: Scene) -> float:
    req_orient = scene.constraints.orientation.lower()
    if candidate.width is None or candidate.height is None or candidate.height == 0:
        return 0.5

    w, h = candidate.width, candidate.height
    is_portrait = h > w
    is_landscape = w > h

    if "portrait" in req_orient:
        if is_portrait:
            return 1.0
        if w == h:
            return 0.5
        return 0.2
    elif "landscape" in req_orient:
        if is_landscape:
            return 1.0
        if w == h:
            return 0.5
        return 0.2
    return 1.0


def _score_resolution(candidate: AssetCandidate, scene: Scene) -> float:
    min_h = scene.constraints.min_height
    if candidate.height is None:
        return 0.5
    if candidate.height >= min_h:
        return 1.0
    if candidate.height > 0:
        return max(0.0, candidate.height / min_h)
    return 0.0


def _score_duration(candidate: AssetCandidate, scene: Scene) -> float:
    min_d = scene.constraints.min_duration_seconds
    max_d = scene.constraints.max_duration_seconds
    dur = candidate.duration_seconds

    if dur is None:
        return 0.5
    if min_d <= dur <= max_d:
        return 1.0
    if dur < min_d and min_d > 0:
        return max(0.0, dur / min_d)
    if dur > max_d:
        # Slightly penalize over-long video clips
        return max(0.5, max_d / dur)
    return 0.0


def _score_source_confidence(candidate: AssetCandidate) -> float:
    if candidate.provider == "local":
        return 1.0
    if candidate.provider in ("pexels", "pixabay"):
        return 0.9 if candidate.rights_status == RightsStatus.PROVIDER_LICENSED else 0.7
    return 0.5
