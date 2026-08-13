"""Tests for candidate ranking and selection (Milestone 7)."""

from __future__ import annotations

from viral_shorts_factory.config.models import AppConfig, RankingWeights
from viral_shorts_factory.domain.assets import AssetCandidate, DownloadVariant, RightsStatus
from viral_shorts_factory.domain.storyboard import Scene, SceneConstraints, Storyboard
from viral_shorts_factory.ranking.ranker import rank_candidates, select_best_candidates
from viral_shorts_factory.ranking.scoring import score_candidate


def make_scene(scene_id: str = "scene_001", query: str = "soccer goalkeeper") -> Scene:
    return Scene(
        scene_id=scene_id,
        order=1,
        purpose="hook",
        target_duration_seconds=3.0,
        spoken_text="Test scene text",
        visual_intent="A goalkeeper saving a ball",
        queries=[query, "football keeper"],
        constraints=SceneConstraints(
            orientation="portrait_preferred",
            min_height=1080,
            min_duration_seconds=2.0,
            max_duration_seconds=15.0,
        ),
    )


def make_candidate(
    candidate_id: str = "pexels:100",
    provider: str = "pexels",
    query: str = "soccer goalkeeper",
    width: int = 1080,
    height: int = 1920,
    duration: float = 5.0,
    rights: RightsStatus = RightsStatus.PROVIDER_LICENSED,
    tags: list[str] | None = None,
) -> AssetCandidate:
    return AssetCandidate(
        candidate_id=candidate_id,
        provider=provider,
        provider_asset_id=candidate_id.split(":")[-1],
        query=query,
        width=width,
        height=height,
        duration_seconds=duration,
        rights_status=rights,
        tags=tags or ["soccer", "goalkeeper"],
        download_variants=[
            DownloadVariant(
                url="https://example.com/v.mp4",
                width=width,
                height=height,
                file_type="video/mp4",
            )
        ],
    )


def test_unverified_candidates_rejected():
    scene = make_scene()
    cand = make_candidate(rights=RightsStatus.UNVERIFIED)
    score = score_candidate(cand, scene, RankingWeights())
    assert score.total == 0.0


def test_deterministic_scoring(config: AppConfig):
    scene = make_scene()
    cand = make_candidate()
    score1 = score_candidate(cand, scene, config.ranking.weights)
    score2 = score_candidate(cand, scene, config.ranking.weights)
    assert score1.total == score2.total
    assert score1.components == score2.components


def test_ranking_order(config: AppConfig):
    scene = make_scene()
    cand_good = make_candidate("pexels:1", width=1080, height=1920, duration=5.0)
    cand_landscape = make_candidate("pexels:2", width=1920, height=1080, duration=5.0)

    ranked = rank_candidates([cand_landscape, cand_good], scene, config)
    assert len(ranked) == 2
    assert ranked[0][0].candidate_id == "pexels:1"
    assert ranked[0][1].total > ranked[1][1].total


def test_species_specific_ranking_rejects_generic_fish(config: AppConfig) -> None:
    scene = make_scene(query="betta fish aquarium")
    generic = make_candidate(
        "pexels:generic",
        query="betta fish aquarium",
        tags=["fish", "aquarium"],
    )
    generic.source_page_url = "https://www.pexels.com/video/fish-on-corals-123/"
    specific = make_candidate(
        "pexels:betta",
        query="betta fish aquarium",
        tags=["betta", "fish", "aquarium"],
    )
    specific.source_page_url = "https://www.pexels.com/video/betta-fish-aquarium-456/"

    ranked = rank_candidates([generic, specific], scene, config)

    assert [candidate.candidate_id for candidate, _score in ranked] == ["pexels:betta"]


def test_species_video_fallback_accepts_aquarium_context(config: AppConfig) -> None:
    scene = make_scene(query="betta fish aquarium")
    candidate = make_candidate(
        "pexels:aquarium-video",
        query="betta fish aquarium",
        tags=["fish", "aquarium"],
    )
    candidate.source_page_url = "https://www.pexels.com/video/fish-in-aquarium-123/"

    score = score_candidate(candidate, scene, config.ranking.weights)

    assert score.total > 0.0
    assert score.components.query_match == 0.25


def test_duplicate_penalty(config: AppConfig):
    scene1 = make_scene("scene_001")
    scene2 = make_scene("scene_002")

    storyboard = Storyboard(scenes=[scene1, scene2])
    cand = make_candidate("pexels:1")

    candidates_by_scene = {
        "scene_001": [cand],
        "scene_002": [cand],
    }

    selection = select_best_candidates(candidates_by_scene, storyboard, config)
    score_scene1 = selection["scene_001"][0][1]
    score_scene2 = selection["scene_002"][0][1]

    # Scene 2 should suffer duplicate penalty since candidate was used in scene 1
    assert score_scene1.total > score_scene2.total
    assert score_scene2.components.duplicate_penalty == 1.0


def test_selection_prefers_unused_candidate_when_available(config: AppConfig) -> None:
    scene1 = make_scene("scene_001")
    scene2 = make_scene("scene_002")
    first = make_candidate("pexels:1")
    second = make_candidate("pexels:2")

    selection = select_best_candidates(
        {
            "scene_001": [first, second],
            "scene_002": [first, second],
        },
        Storyboard(scenes=[scene1, scene2]),
        config,
    )

    assert selection["scene_001"][0][0].candidate_id != selection["scene_002"][0][0].candidate_id


def test_clownfish_specific_ranking_rejects_betta_and_generic_fish(config: AppConfig) -> None:
    scene = make_scene(query="clownfish sea anemone")
    generic = make_candidate(
        "pexels:betta",
        query="clownfish sea anemone",
        tags=["betta", "fish", "aquarium"],
    )
    generic.source_page_url = "https://www.pexels.com/video/betta-fish-aquarium-123/"
    specific = make_candidate(
        "pexels:clownfish",
        query="clownfish sea anemone",
        tags=["clownfish", "fish", "anemone"],
    )
    specific.source_page_url = "https://www.pexels.com/video/clownfish-anemone-456/"

    ranked = rank_candidates([generic, specific], scene, config)

    assert [candidate.candidate_id for candidate, _score in ranked] == ["pexels:clownfish"]


def test_clownfish_video_fallback_requires_anemone_context(config: AppConfig) -> None:
    scene = make_scene(query="clownfish sea anemone")
    candidate = make_candidate(
        "pexels:generic-fish",
        query="clownfish sea anemone",
        tags=["fish", "aquarium"],
    )
    candidate.source_page_url = "https://www.pexels.com/video/fish-in-aquarium-123/"

    assert score_candidate(candidate, scene, config.ranking.weights).total == 0.0


def test_lion_specific_ranking_rejects_unrelated_wildlife(config: AppConfig) -> None:
    scene = make_scene(query="lion close up savanna natural habitat")
    unrelated = [
        make_candidate("pexels:zebra", query=scene.queries[0], tags=["zebra", "wildlife"]),
        make_candidate("pexels:frog", query=scene.queries[0], tags=["frog", "wildlife"]),
        make_candidate("pexels:ant", query=scene.queries[0], tags=["ant", "wildlife"]),
        make_candidate("pexels:forest", query=scene.queries[0], tags=["forest", "wildlife"]),
    ]
    lion = make_candidate(
        "pexels:lion",
        query=scene.queries[0],
        tags=["lion", "wildlife", "savanna"],
    )
    lion.source_page_url = "https://www.pexels.com/video/lion-in-savanna-789/"

    ranked = rank_candidates([*unrelated, lion], scene, config)

    assert [candidate.candidate_id for candidate, _score in ranked] == ["pexels:lion"]
