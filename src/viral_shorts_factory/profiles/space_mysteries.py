"""space_mysteries content profile.

Short-form "unknown space facts / cosmic mysteries" videos (black holes,
planets, galaxies, astronomy). Generates English, stock-footage-friendly visual
queries per beat, plus a deterministic script fixture when the agent has not
written one yet. Visuals deliberately favor public-domain-friendly astronomy
stock (nebula, starry sky, planets, telescopes) that Pexels/Pixabay cover well.
"""

from __future__ import annotations

import re

from viral_shorts_factory.config.models import ProfileConfig
from viral_shorts_factory.domain.script import Beat, BeatType, Script
from viral_shorts_factory.domain.storyboard import Scene, SceneConstraints, Storyboard
from viral_shorts_factory.profiles.base import register_profile

# Canonical English search term -> Indonesian/English aliases. Kept local to this
# profile so astronomy topics don't leak into the shared animal taxonomy
# (domain/topics.py), whose species matching owns that domain.
SPACE_TOPIC_ALIASES: dict[str, tuple[str, ...]] = {
    "black hole": ("lubang hitam", "black hole", "black holes"),
    "white dwarf": ("katai putih", "katai putih", "white dwarf", "white dwarfs"),
    "neutron star": ("bintang neutron", "neutron star", "neutron stars"),
    "pulsar": ("pulsar", "pulsars"),
    "quasar": ("quasar", "quasars"),
    "dark matter": ("materi gelap", "dark matter"),
    "dark energy": ("energi gelap", "dark energy"),
    "wormhole": ("lubang cacing", "wormhole", "wormholes"),
    "galaxy": ("galaksi", "galaxy", "galaxies"),
    "milky way": ("bima sakti", "bima sakti galaxy", "milky way", "milky way galaxy"),
    "nebula": ("nebula", "nebulae"),
    "constellation": ("rasi bintang", "konstelasi", "constellation", "constellations"),
    "solar system": ("tata surya", "solar system"),
    "star": ("bintang", "star", "stars"),
    "sun": ("matahari", "sun", "solar"),
    "moon": ("bulan", "moon", "luna"),
    "planet": ("planet", "planets"),
    "mercury": ("planets merkuri", "merkurius", "mercury"),
    "venus": ("planets venus", "venus", "venus planet"),
    "earth": ("planets bumi", "bumi", "earth", "earth from space"),
    "mars": ("planets mars", "mars", "planet mars"),
    "jupiter": ("planets jupiter", "jupiter", "planet jupiter"),
    "saturn": ("planets saturnus", "saturnus", "saturn", "planet saturn"),
    "uranus": ("planets uranus", "uranus", "planet uranus"),
    "neptune": ("planets neptunus", "neptunus", "neptune", "planet neptune"),
    "dwarf planet": ("planet kerdil", "dwarf planet", "dwarf planets"),
    "exoplanet": ("exoplanet", "exoplanets", "planet ekstrasurya"),
    "asteroid": ("asteroid", "asteroids"),
    "comet": ("komet", "comet", "comets"),
    "meteor": ("meteor", "meteors", "meteorite", "meteorit"),
    "eclipse": ("gerhana", "eclipse", "solar eclipse", "lunar eclipse"),
    "aurora": ("aurora", "aurora borealis", "northern lights"),
    "solar flare": ("badai matahari", "solar flare", "solar storm", "space weather"),
    "gravity": ("gravitasi", "gravity", "gravitational waves", "golombang gravitasi"),
    "space station": ("stasiun luar angkasa", "space station", "iss"),
    "spacecraft": ("pesawat luar angkasa", "spacecraft", "space ship"),
    "rocket": ("roket", "rocket", "rockets", "rocket launch"),
    "astronaut": ("astronot", "astronaut", "astronauts"),
    "telescope": ("teleskop", "telescope", "observatory"),
    "james webb": (
        "teleskop james webb",
        "james webb",
        "james webb space telescope",
        "webb telescope",
    ),
    "voyager": ("voyager",),
    "mars rover": ("penjelajah mars", "mars rover", "curiosity rover", "perseverance rover"),
    "extraterrestrial life": (
        "kehidupan luar angkasa",
        "kehidupan alien",
        "alien life",
        "extraterrestrial",
        "extraterrestrial life",
    ),
}

# Planets are searched as their canonical name; keep "planet X" required
# prefixes out of the canonical so queries read naturally.
_PLANET_PREFIX_STRIP = ("planet ", "planets ")


def _contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _extract_english_topic(topic: str) -> str:
    """Return the canonical English search term for a space topic when known."""
    normalized = " ".join(topic.strip().lower().split())
    entries = sorted(
        SPACE_TOPIC_ALIASES.items(),
        key=lambda item: max((len(alias) for alias in item[1]), default=0),
        reverse=True,
    )
    for canonical, aliases in entries:
        if any(_contains_term(normalized, alias) for alias in aliases):
            return canonical
    if normalized.startswith(_PLANET_PREFIX_STRIP):
        return normalized
    return topic

# Neutral per-purpose visual phrase appended to the topic term when the script
# doesn't supply its own visual_intent. Appending after the topic keeps the
# intent topic-anchored (e.g. "jupiter surrounded by stars") while staying
# generic enough to fit any space topic.
_VISUAL_PHRASES: dict[str, str] = {
    BeatType.HOOK.value: "mysterious close up in deep space",
    BeatType.SETUP.value: "surrounded by stars in deep space",
    BeatType.ESCALATION.value: "dramatic cosmic phenomenon",
    BeatType.PAYOFF.value: "glowing in a cosmic nebula",
    BeatType.CTA.value: "under a vast starry night sky",
}

# Per-purpose query suffixes appended to the topic term, matching how the facts
# profile builds stock-footage-friendly English queries.
_SUFFIX_MAP: dict[str, tuple[str, ...]] = {
    BeatType.HOOK.value: ("deep space", "cosmic nebula", "galaxy stars"),
    BeatType.SETUP.value: ("planet deep space", "astronomy telescope", "solar system"),
    BeatType.ESCALATION.value: ("black hole cosmic", "star formation", "space phenomena"),
    BeatType.PAYOFF.value: ("deep space mystery", "celestial event", "astronomy close up"),
    BeatType.CTA.value: ("starry night sky", "milky way galaxy", "aesthetic space"),
}


def generate_queries(purpose: BeatType, visual_intent: str, topic_term: str) -> list[str]:
    """Generate up to 3 topic-focused, space-themed query variants."""
    suffixes = _SUFFIX_MAP.get(purpose.value, ("deep space", "nebula", "stars"))
    queries = [visual_intent]
    for suffix in suffixes:
        q = f"{topic_term} {suffix}" if topic_term else suffix
        if len(queries) >= 3:
            break
        if q not in queries:
            queries.append(q)
    return queries[:3]


def build_storyboard_from_script(
    script: Script, profile: ProfileConfig, topic: str = "space"
) -> Storyboard:
    """Convert a validated script into a space_mysteries storyboard deterministically."""
    topic_term = _extract_english_topic(topic)
    scenes: list[Scene] = []
    for index, beat in enumerate(script.beats, start=1):
        phrase = _VISUAL_PHRASES.get(beat.type.value, _VISUAL_PHRASES[BeatType.HOOK.value])
        visual = f"{topic_term} {phrase}" if topic_term else phrase
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
                    people_allowed=False,
                ),
            )
        )
    return Storyboard(schema_version="1.0", scenes=scenes)


PROMPT_TEMPLATE = """\
You are the planning stage of Viral Shorts Factory (space_mysteries profile).

Topic: {topic}
Target duration: {target_duration_seconds}s

Write THREE validated JSON artifacts into the project workspace:

1. concept.json  — per docs/03 §2: title, premise, hook, mystery_mechanism,
   payoff, stock_footage_feasibility.
2. script.json   — per docs/03 §3: target_duration_seconds, beats[]. Use beat
   types: hook, setup, payoff, escalation (or reaction), cta. Each beat has an
   id, type, text (in {language}), estimated_seconds.
3. storyboard.json — per docs/03 §4: scenes[]. Each scene: scene_id, order,
   purpose (a beat type), target_duration_seconds, spoken_text, visual_intent
   (English, stock-footage-friendly), queries (3 English variants), constraints
   (portrait_preferred, min_height 1080, people_allowed false).

Narration & Beat Structure Guidelines (CRITICAL):
- Hook (hook): Mind-blowing cosmic contrast/paradox to catch attention instantly.
- Setup (setup): Introduce the subject with scale, context, or mind-boggling
  numbers (distances, temperatures, masses).
- Payoff/Surprise (payoff): Deliver the ironic or unexpected implication behind
  the space fact.
- Escalation/Twist (escalation): Explain the mechanisms/observations behind it.
- Outro (cta): Engaging final thought or question, closing with relevant emojis.

Rules:
- Favor public-domain-friendly astronomy visuals (NASA/space stock) so scenes
  stay stock-footage-feasible; avoid copyrighted mission footage.
- Verify facts against well-documented astronomy sources; do not invent data.
- Spoken text stays in {language}; visual_intent + queries are English.
- Keep total script duration matched to target_duration_seconds.
- schema_version must be "1.0" on every artifact.
"""


def build_script_fixture(topic: str, target_duration_seconds: float) -> Script:
    """Deterministic 5-beat script fixture for space_mysteries profile."""
    return Script(
        schema_version="1.0",
        target_duration_seconds=target_duration_seconds,
        beats=[
            Beat(
                id="beat_001",
                type=BeatType.HOOK,
                text=(
                    f"Tahukah kamu misteri terbesar tentang {topic} yang jarang orang"
                    " sangka?"
                ),
                estimated_seconds=target_duration_seconds * 0.18,
            ),
            Beat(
                id="beat_002",
                type=BeatType.SETUP,
                text=(
                    f"{topic.capitalize()} punya skala yang membuat angka biasa terasa"
                    " tidak berarti di alam semesta."
                ),
                estimated_seconds=target_duration_seconds * 0.30,
            ),
            Beat(
                id="beat_003",
                type=BeatType.PAYOFF,
                text=(
                    f"Tapi imbas paling mengejutkan dari {topic} justru sesuatu yang"
                    " tidak terlihat secara langsung!"
                ),
                estimated_seconds=target_duration_seconds * 0.22,
            ),
            Beat(
                id="beat_004",
                type=BeatType.ESCALATION,
                text=(
                    f"Para astronom baru menyadari bahwa {topic} dipengaruhi oleh"
                    " mekanisme luar biasa jauh di balik tata surya kita."
                ),
                estimated_seconds=target_duration_seconds * 0.20,
            ),
            Beat(
                id="beat_005",
                type=BeatType.CTA,
                text=(
                    f"Menurutmu, misteri {topic} mana yang paling bikin merinding?"
                    " 🌌✨"
                ),
                estimated_seconds=target_duration_seconds * 0.10,
            ),
        ],
    )


# Register so vsf plan can resolve this profile by name.
register_profile("space_mysteries", build_storyboard_from_script, build_script_fixture)