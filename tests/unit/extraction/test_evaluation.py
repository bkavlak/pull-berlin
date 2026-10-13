from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.extraction.evaluation import LabelledText, evaluate

RENT = Proposition(ClaimType.IS_RENTABLE_FOR_PRIVATE_EVENTS)


def labelled(text: str, rent: bool) -> LabelledText:
    return LabelledText(text=text, labels={RENT: rent})


GOLD = [labelled("a", True), labelled("b", True), labelled("c", False), labelled("d", False)]


def test_perfect_classifier_scores_one() -> None:
    (score,) = evaluate(GOLD, [{RENT: 1.0}, {RENT: 1.0}, {RENT: 0.0}, {RENT: 0.0}])
    assert (score.precision, score.recall, score.f1, score.brier) == (1.0, 1.0, 1.0, 0.0)


def test_false_positive_lowers_precision_not_recall() -> None:
    (score,) = evaluate(GOLD, [{RENT: 0.9}, {RENT: 0.9}, {RENT: 0.9}, {RENT: 0.1}])
    assert score.precision == pytest.approx(2 / 3)
    assert score.recall == 1.0


def test_brier_score_punishes_confident_mistakes() -> None:
    (confident,) = evaluate(GOLD, [{RENT: 1.0}, {RENT: 1.0}, {RENT: 1.0}, {RENT: 0.0}])
    (hedged,) = evaluate(GOLD, [{RENT: 1.0}, {RENT: 1.0}, {RENT: 0.6}, {RENT: 0.0}])
    assert confident.brier > hedged.brier


def test_counts_are_reported_for_judging_how_much_the_numbers_mean() -> None:
    (score,) = evaluate(GOLD, [{RENT: 1.0}] * 4)
    assert (score.n, score.positives, score.predicted_positives) == (4, 2, 4)


def test_unlabelled_propositions_are_not_scored() -> None:
    gold = [LabelledText(text="a", labels={})]
    assert evaluate(gold, [{RENT: 1.0}]) == []


def test_no_predicted_positives_gives_zero_precision_not_a_crash() -> None:
    (score,) = evaluate(GOLD, [{RENT: 0.0}] * 4)
    assert (score.precision, score.recall, score.f1) == (0.0, 0.0, 0.0)
