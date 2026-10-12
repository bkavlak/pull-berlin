"""Port of the extraction context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from pull_berlin.catalog.domain.claim import Proposition

Judgement = Mapping[Proposition, float]
"""Probability, per proposition, that the text asserts it."""


class TextClassifier(Protocol):
    """Reads texts and judges which propositions each text asserts. One judgement per text, in order."""

    @property
    def model_id(self) -> str: ...

    def classify(self, texts: Sequence[str]) -> list[Judgement]: ...
