"""Shared topic normalization and subject aliases for nature/facts content."""

from __future__ import annotations

import re

# Categories are normalized for provider search but are intentionally not
# subject-locked: a category such as "mamalia" legitimately contains many
# different animals.
TOPIC_ALIASES: dict[str, tuple[str, ...]] = {
    "mammals": ("mamalia", "mammal", "mammals"),
    "reptiles": ("reptil", "reptile", "reptiles"),
    "amphibians": ("amfibi", "amphibian", "amphibians"),
    "fish": ("ikan", "fish"),
    "insects": ("serangga", "serangga", "insect", "insects"),
    "birds": ("burung", "bird", "birds"),
    "marine animals": (
        "hewan laut lainnya",
        "hewan laut",
        "marine animals",
        "marine animal",
    ),
    "unique animals": ("hewan unik", "unique animals", "unique animal"),
    "lion": ("singa", "lion", "lions"),
    "sea lion": ("singa laut", "sea lion", "sea lions"),
    "tiger": ("harimau", "tiger", "tigers"),
    "elephant": ("gajah", "elephant", "elephants"),
    "cute cat": ("kucing", "cat", "cats"),
    "dog pet": ("anjing", "dog", "dogs"),
    "horse": ("kuda", "horse", "horses"),
    "cow": ("sapi", "cow", "cows"),
    "goat": ("kambing", "goat", "goats"),
    "sheep": ("domba", "sheep"),
    "buffalo": ("kerbau", "buffalo", "buffaloes"),
    "deer": ("rusa", "deer"),
    "giraffe": ("jerapah", "giraffe", "giraffes"),
    "zebra": ("zebra", "zebras"),
    "monkey": ("monyet", "monkey", "monkeys"),
    "orangutan": ("orangutan", "orang utan", "orangutans"),
    "gorilla": ("gorila", "gorilla", "gorillas"),
    "panda": ("panda", "pandas"),
    "koala": ("koala", "koalas"),
    "rabbit": ("kelinci", "rabbit", "rabbits"),
    "rat": ("tikus", "rat", "rats"),
    "bat": ("kelelawar", "bat", "bats"),
    "dolphin": ("lumba-lumba", "lumba lumba", "dolphin", "dolphins"),
    "whale": ("ikan paus", "paus", "whale", "whales"),
    "dugong": ("dugong",),
    "bear": ("beruang", "bear", "bears"),
    "eagle": ("elang", "rajawali", "eagle", "eagles"),
    "pigeon": ("merpati", "pigeon", "pigeons"),
    "chicken": ("ayam", "chicken", "chickens"),
    "duck": ("bebek", "duck", "ducks"),
    "goose": ("angsa", "goose", "geese"),
    "owl": ("burung hantu", "owl", "owls"),
    "cockatoo": ("kakaktua", "kakatua", "cockatoo", "cockatoos"),
    "canary": ("kenari", "canary", "canaries"),
    "bird of paradise": ("cenderawasih", "bird of paradise", "birds of paradise"),
    "starling": ("jalak", "starling", "starlings"),
    "pelican": ("pelikan", "pelican", "pelicans"),
    "flamingo": ("flamingo", "flamingos"),
    "penguin": ("penguin", "penguins"),
    "cassowary": ("kasuari", "cassowary", "cassowaries"),
    "crocodile": ("buaya", "crocodile", "crocodiles"),
    "snake": ("ular", "snake", "snakes"),
    "lizard": ("kadal", "lizard", "lizards"),
    "komodo dragon": ("komodo", "komodo dragon", "komodo dragons"),
    "iguana": ("iguana", "iguanas"),
    "chameleon": ("bunglon", "chameleon", "chameleons"),
    "turtle": ("kura-kura", "kura kura", "turtle", "turtles"),
    "sea turtle": ("penyu", "sea turtle", "sea turtles"),
    "gecko": ("tokek", "gecko", "geckos"),
    "frog": ("katak", "frog", "frogs"),
    "toad": ("kodok", "toad", "toads"),
    "salamander": ("salamander", "salamanders"),
    "caecilian": ("sesilia", "caecilian", "caecilians"),
    "shark": ("ikan hiu", "hiu", "shark", "sharks"),
    "tuna fish": ("ikan tuna", "tuna", "tuna fish"),
    "catfish": ("ikan lele", "lele", "catfish", "catfishes"),
    "common carp": ("ikan mas", "common carp", "carp"),
    "betta fish": ("ikan cupang", "cupang", "beta", "beta fish", "betta", "betta fish"),
    "koi fish": ("ikan koi", "koi", "koi fish"),
    "gourami": ("ikan gurame", "gurame", "gourami", "gouramis"),
    "salmon": ("ikan salmon", "salmon", "salmons"),
    "stingray": ("ikan pari", "pari", "stingray", "stingrays"),
    "clownfish": (
        "ikan badut",
        "clownfish",
        "clown fish",
        "ocellaris",
        "amphiprion",
        "nemo",
    ),
    "octopus": ("gurita", "octopus", "octopuses"),
    "squid": ("cumi-cumi", "cumi cumi", "squid", "squids"),
    "jellyfish": ("ubur-ubur", "ubur ubur", "jellyfish"),
    "starfish": ("bintang laut", "starfish", "starfishes"),
    "crab": ("kepiting", "crab", "crabs"),
    "shrimp": ("udang", "shrimp", "shrimps"),
    "lobster": ("lobster", "lobsters"),
    "clam": ("kerang", "clam", "clams"),
    "sea snail": ("siput laut", "sea snail", "sea snails"),
    "sea cucumber": ("teripang", "sea cucumber", "sea cucumbers"),
    "platypus": ("platipus", "platypus", "platypuses"),
    "axolotl": ("axolotl", "axolotls"),
    "hedgehog": ("landak", "hedgehog", "hedgehogs"),
    "pangolin": ("trenggiling", "pangolin", "pangolins"),
    "armadillo": ("armadillo", "armadillos"),
    "sloth": ("sloth", "sloths"),
    "aye-aye": ("aye-aye", "aye aye"),
    "narwhal": ("narwhal", "narwhals"),
    "okapi": ("okapi", "okapis"),
    "wombat": ("wombat", "wombats"),
    "tarsier": ("tarsius", "tarsier", "tarsiers"),
}

_CATEGORY_KEYS = {
    "mammals",
    "reptiles",
    "amphibians",
    "fish",
    "insects",
    "birds",
    "marine animals",
    "unique animals",
}

# Subject names may differ from the search phrase used in a storyboard. For
# example, "cute cat" searches should be locked as the subject "cat".
_SPECIES_TOPIC_KEYS = {
    "cat": "cute cat",
    "dog": "dog pet",
    "betta": "betta fish",
}

SPECIES_ALIASES: dict[str, tuple[str, ...]] = {
    **{
        species: TOPIC_ALIASES[topic_key]
        for species, topic_key in _SPECIES_TOPIC_KEYS.items()
    },
    **{
        canonical: aliases
        for canonical, aliases in TOPIC_ALIASES.items()
        if canonical not in _CATEGORY_KEYS and canonical not in _SPECIES_TOPIC_KEYS.values()
    },
}


def _contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def normalize_topic(topic: str) -> str:
    """Return the canonical English search term for a user topic when known."""
    normalized = " ".join(topic.strip().lower().split())
    entries = sorted(
        TOPIC_ALIASES.items(),
        key=lambda item: max((len(alias) for alias in item[1]), default=0),
        reverse=True,
    )
    for canonical, aliases in entries:
        if any(_contains_term(normalized, alias) for alias in aliases):
            return canonical
    return topic


def matches_species(tokens: set[str], species: str) -> bool:
    """Return whether provider metadata tokens identify the requested species."""
    aliases = SPECIES_ALIASES.get(species, ())
    for alias in aliases:
        alias_tokens = set(re.findall(r"[a-z0-9]+", alias.lower()))
        if alias_tokens and alias_tokens.issubset(tokens):
            return True
    return False


def required_species(query_text: str) -> str | None:
    """Extract a known species subject from a scene's complete query text."""
    normalized = " ".join(query_text.lower().split())
    entries = sorted(
        SPECIES_ALIASES.items(),
        key=lambda item: max((len(alias) for alias in item[1]), default=0),
        reverse=True,
    )
    for species, aliases in entries:
        if any(_contains_term(normalized, alias) for alias in aliases):
            return species
    return None
