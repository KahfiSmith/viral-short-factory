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


def test_unknown_topic_is_preserved() -> None:
    assert normalize_topic("hewan khayalan") == "hewan khayalan"
