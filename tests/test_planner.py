"""Query planner tests."""

from __future__ import annotations

import logging

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.script import Beat, BeatType, Script
from viral_shorts_factory.pipeline.planner import plan_queries
from viral_shorts_factory.profiles.football_comedy import build_storyboard_from_script


def _script() -> Script:
    return Script(
        schema_version="1.0",
        target_duration_seconds=28.0,
        beats=[
            Beat(id="b1", type=BeatType.HOOK, text="Hook.", estimated_seconds=4.0),
            Beat(id="b2", type=BeatType.PAYOFF, text="Payoff.", estimated_seconds=24.0),
        ],
    )


def test_plan_queries_one_per_scene(config: AppConfig) -> None:
    profile = config.profiles["football_comedy"]
    storyboard = build_storyboard_from_script(_script(), profile)
    requests = plan_queries(storyboard, config)

    assert len(requests) == 4  # 2 scenes * (1 video req + 1 image req)
    first = requests[0]
    assert first.scene_id == "scene_001"
    assert first.query  # first query variant
    assert first.orientation == "portrait"
    assert first.minimum_height == 1080
    assert first.max_results == 8
    image = requests[1]
    assert image.media_type.value == "image"
    assert image.max_results == 4


def test_plan_queries_respects_constraints(config: AppConfig) -> None:
    profile = config.profiles["football_comedy"]
    storyboard = build_storyboard_from_script(_script(), profile)
    storyboard.scenes[0].constraints.min_height = 720
    requests = plan_queries(storyboard, config)
    assert requests[0].minimum_height == 720


def test_plan_queries_emits_event(config: AppConfig) -> None:
    import tempfile
    from pathlib import Path

    from viral_shorts_factory.domain.project import Project
    from viral_shorts_factory.pipeline.context import PipelineContext

    profile = config.profiles["football_comedy"]
    storyboard = build_storyboard_from_script(_script(), profile)
    tmp = Path(tempfile.mkdtemp())
    ctx = PipelineContext(
        project=Project(
            project_id="p1",
            profile="football_comedy",
            topic="t",
            target_duration_seconds=28,
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        ),
        config=config,
        workspace_dir=tmp,
    )
    # Ensure the emit goes to a captured log.
    logger = logging.getLogger("vsf.pipeline")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(tmp / "run.jsonl")
    logger.addHandler(handler)
    plan_queries(storyboard, config, context=ctx)
    logger.removeHandler(handler)
    handler.close()
    lines = (tmp / "run.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert any("queries_planned" in line for line in lines)
