"""Runs the real Laya model. Skipped unless the `laya` extra is installed (`uv sync --extra laya`)."""

from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.claim import ClaimType, Proposition

pytest.importorskip("laya")

from pull_berlin.extraction.laya_classifier import LayaClassifier

HIRE = Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)


@pytest.fixture(scope="module")
def laya() -> LayaClassifier:
    return LayaClassifier()


def test_explicit_german_rental_offer_is_judged_hireable(laya: LayaClassifier) -> None:
    (judgement,) = laya.classify(
        [
            "Unsere Eventlocation in Kreuzberg können Sie für Hochzeiten, "
            "Firmenfeiern und private Partys mieten."
        ]
    )
    assert judgement[HIRE] > 0.5


def test_bakery_text_is_not_judged_hireable(laya: LayaClassifier) -> None:
    (judgement,) = laya.classify(["Frische Brötchen und Kuchen, Montag bis Samstag ab 7 Uhr."])
    assert judgement[HIRE] < 0.5
