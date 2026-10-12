"""Scores a classifier's judgements against labelled texts: precision, recall, F1 and Brier score.

Brier (mean squared error of the probability) matters as much as F1 here: the catalog uses the
probabilities as evidence strength, so a confidently wrong classifier does real damage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pull_berlin.catalog.domain.claim import Proposition
from pull_berlin.extraction.ports import Judgement


@dataclass(frozen=True)
class LabelledText:
    text: str
    labels: Mapping[Proposition, bool]
    url: str = ""


@dataclass(frozen=True)
class Score:
    proposition: Proposition
    n: int
    positives: int
    predicted_positives: int
    precision: float
    recall: float
    f1: float
    brier: float


def evaluate(
    gold: Sequence[LabelledText], judgements: Sequence[Judgement], threshold: float = 0.5
) -> list[Score]:
    if len(gold) != len(judgements):
        raise ValueError(f"{len(gold)} labelled texts but {len(judgements)} judgements")
    propositions = sorted({p for item in gold for p in item.labels}, key=lambda p: p.label)
    scores = []
    for proposition in propositions:
        pairs = [
            (item.labels[proposition], judgement.get(proposition, 0.0))
            for item, judgement in zip(gold, judgements, strict=True)
            if proposition in item.labels
        ]
        true_pos = sum(1 for truth, p in pairs if truth and p >= threshold)
        predicted = sum(1 for _, p in pairs if p >= threshold)
        positives = sum(1 for truth, _ in pairs if truth)
        precision = true_pos / predicted if predicted else 0.0
        recall = true_pos / positives if positives else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        brier = sum((p - float(truth)) ** 2 for truth, p in pairs) / len(pairs)
        scores.append(Score(proposition, len(pairs), positives, predicted, precision, recall, f1, brier))
    return scores
