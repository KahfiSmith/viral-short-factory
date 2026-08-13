"""facts / education content profile.

For short-form "did you know" fact videos (nature, animals, science). Generates
English, stock-footage-friendly visual queries per beat, plus a deterministic
script fixture when the agent has not written one yet.
"""

from __future__ import annotations

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import Beat, BeatType, Script
from viral_shorts_factory.domain.storyboard import Scene, SceneConstraints, Storyboard
from viral_shorts_factory.profiles.base import register_profile

def _extract_english_topic(topic: str) -> str:
    """Extract stock-friendly English search terms from topic string."""
    t = topic.lower()
    if "cupang" in t or "betta" in t:
        return "betta fish"
    if "kucing" in t or "cat" in t:
        return "cute cat"
    if "anjing" in t or "dog" in t:
        return "dog pet"
    return topic


def generate_queries(purpose: BeatType, visual_intent: str, topic_term: str) -> list[str]:
    """Generate up to 3 query variants dynamically for a facts scene."""
    suffix_map = {
        BeatType.HOOK.value: ["macro close up", "swimming underwater", "beautiful colors"],
        BeatType.SETUP.value: ["underwater macro", "aquarium tank", "swimming close up"],
        BeatType.PAYOFF.value: ["behavior close up", "macro detail", "underwater shot"],
        BeatType.ESCALATION.value: ["action swimming", "fast movement", "macro high quality"],
        BeatType.CTA.value: ["peaceful aquarium", "aesthetic cinematic", "floating water"],
    }
    suffixes = suffix_map.get(purpose.value, ["underwater", "close up", "aquarium"])
    queries = [visual_intent]
    for s in suffixes:
        q = f"{topic_term} {s}"
        if len(queries) >= 3:
            break
        if q not in queries:
            queries.append(q)
    return queries[:3]


def build_storyboard_from_script(script: Script, profile: ProfileConfig, topic: str = "nature") -> Storyboard:
    """Convert a validated script into a facts storyboard deterministically."""
    scenes: list[Scene] = []
    topic_term = _extract_english_topic(topic)

    for index, beat in enumerate(script.beats, start=1):
        visual = f"{topic_term} {beat.type.value} macro underwater video"
        scenes.append(
            Scene(
                scene_id=f"scene_{index:03d}",
                order=index,
                purpose=beat.type,
                target_duration_seconds=beat.estimated_seconds,
                spoken_text=beat.text,
                visual_intent=visual,
                queries=generate_queries(beat.type, visual, topic_term),
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
You are the planning stage of Viral Shorts Factory (facts profile).

Topic: {topic}
Target duration: {target_duration_seconds}s

Write THREE validated JSON artifacts into the project workspace:

1. concept.json  — per docs/03 §2: title, premise, hook, comedy_mechanism,
   payoff, stock_footage_feasibility.
2. script.json   — per docs/03 §3: target_duration_seconds, beats[]. Use beat
   types: hook, setup, payoff, escalation (or reaction), cta. Each beat has an id,
   type, text (in {language}), estimated_seconds.
3. storyboard.json — per docs/03 §4: scenes[]. Each scene: scene_id, order,
   purpose (a beat type), target_duration_seconds, spoken_text, visual_intent
   (English, stock-footage-friendly), queries (3 English variants), constraints.

Narration & Beat Structure Guidelines (CRITICAL):
- Hook (hook): Mind-blowing opening contrast/paradox or dramatic statement to catch attention instantly.
- Setup (setup): Introduce the subject in detail with scale, context, or mind-boggling numbers.
- Payoff/Surprise (payoff): Deliver the ironic or unexpected limitation/secret behind the subject.
- Escalation/Twist (escalation): Explain the twist or adaptation resulting from that limitation.
- Outro (cta): Humorous/engaging final thought or question, closing with relevant emojis.

Rules:
- Spoken text stays in {language}; visual_intent + queries are English.
- Keep total script duration matched to target_duration_seconds.
- schema_version must be "1.0" on every artifact.
"""


def build_script_fixture(topic: str, target_duration_seconds: float) -> Script:
    """Deterministic 5-beat script fixture for facts profile."""
    return Script(
        schema_version="1.0",
        target_duration_seconds=target_duration_seconds,
        beats=[
            Beat(
                id="beat_001",
                type=BeatType.HOOK,
                text=f"Tahukah kamu fakta paling menakjubkan tentang {topic} yang jarang orang tahu?",
                estimated_seconds=target_duration_seconds * 0.18,
            ),
            Beat(
                id="beat_002",
                type=BeatType.SETUP,
                text=f"{topic.capitalize()} memiliki keunikan luar biasa yang membuatnya sangat istimewa di alam liar.",
                estimated_seconds=target_duration_seconds * 0.30,
            ),
            Beat(
                id="beat_003",
                type=BeatType.PAYOFF,
                text=f"Tapi rahasia paling mengejutkan dari {topic} adalah kemampuan bertahan hidup dan perilakunya yang tidak terduga!",
                estimated_seconds=target_duration_seconds * 0.22,
            ),
            Beat(
                id="beat_004",
                type=BeatType.ESCALATION,
                text=f"Plot twist-nya? Para peneliti menemukan fakta bahwa kebiasaan {topic} ini justru sangat membantu ekosistem sekitarnya.",
                estimated_seconds=target_duration_seconds * 0.20,
            ),
            Beat(
                id="beat_005",
                type=BeatType.CTA,
                text=f"Menurutmu, fakta mana dari {topic} yang paling bikin kamu terheran-heran? 💡✨",
                estimated_seconds=target_duration_seconds * 0.10,
            ),
        ],
    )


# Register so vsf plan can resolve this profile by name.
register_profile("facts", build_storyboard_from_script, build_script_fixture)
