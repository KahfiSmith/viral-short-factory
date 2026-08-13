"""Query planner: storyboard scenes -> provider-agnostic search requests.

Emits a structured `queries_planned` event per project run and returns the
AssetSearchRequest list that the asset-discovery stage (M7) will execute against
the local library and network providers.
"""

from __future__ import annotations

from viral_shorts_factory.config.models import AppConfig
from viral_shorts_factory.domain.assets import AssetSearchRequest
from viral_shorts_factory.domain.storyboard import Storyboard
from viral_shorts_factory.pipeline.context import PipelineContext


def plan_queries(
    storyboard: Storyboard,
    config: AppConfig,
    context: PipelineContext | None = None,
) -> list[AssetSearchRequest]:
    """Turn each storyboard scene into video + image AssetSearchRequests.

    Emits two requests per scene:
    1. Video request (target 8 videos)
    2. Image request (target 3 images)
    """
    from viral_shorts_factory.domain.assets import MediaType

    requests: list[AssetSearchRequest] = []
    for scene in storyboard.scenes:
        constraints = scene.constraints
        orientation = (
            "portrait"
            if "portrait" in constraints.orientation
            else constraints.orientation
        )
        # Request 8 videos per scene
        requests.append(
            AssetSearchRequest(
                scene_id=scene.scene_id,
                query=scene.queries[0],
                media_type=MediaType.VIDEO,
                locale="en-US",
                orientation=orientation,
                minimum_height=constraints.min_height,
                max_results=8,
            )
        )
        # Request 3 images per scene
        requests.append(
            AssetSearchRequest(
                scene_id=scene.scene_id,
                query=scene.queries[0],
                media_type=MediaType.IMAGE,
                locale="en-US",
                orientation=orientation,
                minimum_height=constraints.min_height,
                max_results=3,
            )
        )
    if context is not None:
        context.emit(
            "queries_planned",
            count=len(requests),
            scenes=[r.scene_id for r in requests],
        )
    return requests
