"""football_comedy content profile (docs/01-PROJECT-SPEC, docs/05 M6).

This module owns the profile's story template and the deterministic query
generator contract. The AI coding agent fills concept/script/storyboard JSON
artifacts using PROMPT_TEMPLATE; Python validates and executes them. No LLM
vendor calls live in domain logic.
"""

from __future__ import annotations

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import BeatType, Script
from viral_shorts_factory.domain.storyboard import Scene, SceneConstraints, Storyboard
from viral_shorts_factory.profiles.base import register_profile

# Per-purpose query variant templates. Each produces English, stock-footage-
# friendly queries (docs/04 §7: English visual queries perform better).
_QUERY_TEMPLATES: dict[str, list[str]] = {
    BeatType.HOOK.value: [
        "amateur goalkeeper confident",
        "football goalkeeper standing field",
        "soccer goalkeeper walking onto pitch",
    ],
    BeatType.SETUP.value: [
        "football goalkeeper training",
        "soccer keeper practice session",
        "goalkeeper warming up goal",
    ],
    BeatType.ESCALATION.value: [
        "football goalkeeper running out",
        "soccer keeper rushing forward",
        "goalkeeper charging off line",
    ],
    BeatType.PAYOFF.value: [
        "goalkeeper save reaction",
        "soccer keeper dives ball",
        "football keeper miss goal",
    ],
    BeatType.REACTION.value: [
        "soccer fans reaction crowd",
        "football supporters celebrating",
        "amateur football team celebrating",
    ],
    BeatType.CTA.value: [
        "football stadium wide shot",
        "soccer field aerial",
        "football pitch sunset",
    ],
}

# Default visual intent per beat, used when the script doesn't specify one.
_DEFAULT_VISUAL: dict[str, str] = {
    BeatType.HOOK.value: "amateur goalkeeper standing confidently on a football field",
    BeatType.SETUP.value: "goalkeeper warming up during a casual football match",
    BeatType.ESCALATION.value: "goalkeeper running far out of his goal",
    BeatType.PAYOFF.value: "goalkeeper failing to reach the ball, comedy moment",
    BeatType.REACTION.value: "teammates and onlookers reacting",
    BeatType.CTA.value: "wide shot of a football pitch",
}


def generate_queries(purpose: BeatType, visual_intent: str) -> list[str]:
    """Generate up to 3 query variants for a scene (the query generator contract).

    Uses the per-purpose templates; a custom visual_intent prepends the first
    variant so the intent is never lost.
    """
    templates = _QUERY_TEMPLATES.get(purpose.value, _QUERY_TEMPLATES[BeatType.HOOK.value])
    queries = [visual_intent]
    for t in templates:
        if len(queries) >= 3:
            break
        if t not in queries:
            queries.append(t)
    return queries[:3]


def build_storyboard_from_script(
    script: Script, profile: ProfileConfig, topic: str = ""
) -> Storyboard:
    """Convert a validated script into a storyboard deterministically."""
    del topic  # Football visuals are profile-defined, not topic-defined.
    scenes: list[Scene] = []
    for index, beat in enumerate(script.beats, start=1):
        visual = _DEFAULT_VISUAL.get(beat.type.value, beat.text)
        scenes.append(
            Scene(
                scene_id=f"scene_{index:03d}",
                order=index,
                purpose=beat.type,
                target_duration_seconds=beat.estimated_seconds,
                spoken_text=beat.text,
                visual_intent=visual,
                queries=generate_queries(beat.type, visual),
                constraints=SceneConstraints(
                    orientation="portrait_preferred",
                    min_height=1080,
                    min_duration_seconds=max(2.0, profile.min_duration_seconds * 0.3),
                    max_duration_seconds=profile.max_duration_seconds,
                    people_allowed=True,
                ),
            )
        )
    return Storyboard(schema_version="1.0", scenes=scenes)


PROMPT_TEMPLATE = """\
You are the planning stage of Viral Shorts Factory.

Profile: {profile} ({language})
Topic: {topic}
Target duration: {target_duration_seconds}s

Write THREE validated JSON artifacts into the project workspace:

1. concept.json  — per docs/03 §2: title, premise, hook, comedy_mechanism,
   payoff, stock_footage_feasibility.
2. script.json   — per docs/03 §3: target_duration_seconds, beats[]. Use beat
   types: hook, setup, escalation, payoff, reaction, cta. Each beat has an id,
   type, text (in {language}), estimated_seconds.
3. storyboard.json — per docs/03 §4: scenes[]. Each scene: scene_id, order,
   purpose (a beat type), target_duration_seconds, spoken_text, visual_intent
   (English, stock-footage-friendly), queries (3 English variants), constraints
   (orientation portrait_preferred, min_height 1080, min_duration_seconds,
   max_duration_seconds, people_allowed).

Rules:
- Total script duration must match target_duration_seconds within ~10%%.
- Spoken text stays in {language}; visual_intent + queries are English.
- Keep it stock-footage-feasible: no match-broadcast or copyrighted clips.
- For {profile}: expectation-vs-reality comedy; fast opening hook; strong
  reaction/punchline retention.
- Do not run any pipeline commands. Only write the three JSON files.
- schema_version must be "1.0" on every artifact.
"""


def build_script_fixture(topic: str, target_duration_seconds: float) -> Script:
    """Deterministic 4-beat script for the profile (used by CLI `plan` when no
    script.json exists yet, and by tests)."""
    from viral_shorts_factory.domain.script import Beat
    from viral_shorts_factory.domain.script import Script as ScriptModel

    return ScriptModel(
        schema_version="1.0",
        target_duration_seconds=target_duration_seconds,
        beats=[
            Beat(
                id="beat_001",
                type=BeatType.HOOK,
                text=f"Kiper baru kita katanya {topic}.",
                estimated_seconds=target_duration_seconds * 0.15,
            ),
            Beat(
                id="beat_002",
                type=BeatType.SETUP,
                text="Dia langsung keluar dari gawang buat jemput bola.",
                estimated_seconds=target_duration_seconds * 0.25,
            ),
            Beat(
                id="beat_003",
                type=BeatType.ESCALATION,
                text="Semakin jauh dia dari gawang, semakin yakin dia.",
                estimated_seconds=target_duration_seconds * 0.30,
            ),
            Beat(
                id="beat_004",
                type=BeatType.PAYOFF,
                text="Dan bola pun... masuk. Kepercayaan diri jauh di atas kemampuan.",
                estimated_seconds=target_duration_seconds * 0.30,
            ),
        ],
    )


# Register so vsf plan can resolve this profile by name.
register_profile("football_comedy", build_storyboard_from_script, build_script_fixture)
