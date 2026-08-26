"""Tests for the shared animal topic taxonomy."""

from __future__ import annotations

import pytest

from viral_shorts_factory.domain.topics import TOPIC_ALIASES, normalize_topic


@pytest.mark.parametrize(
    ("canonical", "alias"),
    [
        (canonical, alias)
        for canonical, aliases in TOPIC_ALIASES.items()
        for alias in aliases
    ],
)
def test_every_taxonomy_alias_normalizes(canonical: str, alias: str) -> None:
    assert normalize_topic(alias) == canonical


def test_specific_phrases_beat_broader_category_aliases() -> None:
    assert normalize_topic("ikan paus (mamalia laut, bukan ikan)") == "whale"
    assert normalize_topic("burung hantu") == "owl"
    assert normalize_topic("ikan cupang") == "betta fish"
    assert normalize_topic("ikan badut") == "clownfish"
    assert normalize_topic("singa laut") == "sea lion"
    assert normalize_topic("orca") == "orca"
    assert normalize_topic("white shark") == "great white shark"
    assert normalize_topic("beruang grizzly") == "grizzly bear"
    assert normalize_topic("jaguar") == "jaguar"
    assert normalize_topic("anaconda") == "anaconda"
    assert normalize_topic("luwak madu") == "honey badger"
    assert normalize_topic("beruang kutub") == "polar bear"
    assert normalize_topic("kuda nil") == "hippopotamus"
    assert normalize_topic("hyena") == "spotted hyena"
    assert normalize_topic("wolverine") == "wolverine"
    assert normalize_topic("buaya muara") == "saltwater crocodile"
    assert normalize_topic("hiu banteng") == "bull shark"
    assert normalize_topic("ubur-ubur kotak") == "box jellyfish"
    assert normalize_topic("black mamba") == "black mamba"
    assert normalize_topic("king cobra") == "king cobra"
    assert normalize_topic("ular kobra") == "king cobra"
    assert normalize_topic("badak") == "rhinoceros"
    assert normalize_topic("rhino") == "rhinoceros"
    assert normalize_topic("komodo") == "komodo dragon"
    assert normalize_topic("inland taipan") == "inland taipan"
    assert normalize_topic("elang harpy") == "harpy eagle"
    assert normalize_topic("serigala") == "wolf"
    assert normalize_topic("citah") == "cheetah"
    assert normalize_topic("macan tutul") == "leopard"
    assert normalize_topic("singa gunung") == "cougar"
    assert normalize_topic("puma") == "cougar"


def test_unknown_topic_is_preserved() -> None:
    assert normalize_topic("hewan khayalan") == "hewan khayalan"
