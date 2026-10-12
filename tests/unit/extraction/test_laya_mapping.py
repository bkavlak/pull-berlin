from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.extraction.laya_classifier import from_laya_answers, to_laya_schema
from pull_berlin.extraction.questions import QUESTION_SET_V1

SCHEMA = to_laya_schema(QUESTION_SET_V1)


def test_yes_no_questions_become_laya_noul_questions() -> None:
    hire = SCHEMA["is_hireable_for_private_events"]
    assert hire["type"] == "noul"
    assert "rent" in hire["instructions"]


def test_category_question_becomes_a_laya_choice_over_category_values() -> None:
    category = SCHEMA["space_category"]
    assert category["type"] == "choice"
    assert set(category["criteria"]) == {c.value for c in SpaceCategory}


def test_noul_probability_maps_back_to_its_proposition() -> None:
    answers = {
        "is_hireable_for_private_events": {"type": "noul", "noul": 0.91},
        "hosts_evening_events": {"type": "noul", "noul": 0.12},
        "operates_past_midnight": {"type": "noul", "noul": 0.05},
        "space_category": {"type": "choice", "choice": "loft", "probabilities": {"loft": 0.7, "bar": 0.3}},
    }
    judgement = from_laya_answers(answers, QUESTION_SET_V1)
    assert judgement[Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)] == 0.91
    assert judgement[Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.LOFT)] == 0.7


def test_missing_answer_is_a_clear_error_not_a_silent_zero() -> None:
    with pytest.raises(KeyError, match="hosts_evening_events"):
        from_laya_answers({"is_hireable_for_private_events": {"noul": 0.5}}, QUESTION_SET_V1)
