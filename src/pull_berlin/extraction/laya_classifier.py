"""Laya adapter for the TextClassifier port (https://github.com/NandhaKishorM/laya, Apache-2.0).

Laya answers typed questions over a text in one forward pass with calibrated probabilities.
Install with `uv sync --extra laya`. The schema mapping below is pure and unit tested; only
`LayaClassifier` touches the model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.extraction.ports import Judgement
from pull_berlin.extraction.questions import QUESTION_SET_V1, QuestionSet


def to_laya_schema(questions: QuestionSet) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {
        q.key: {"type": "noul", "instructions": q.instructions} for q in questions.yes_no
    }
    schema[questions.category.key] = {
        "type": "choice",
        "instructions": questions.category.instructions,
        "criteria": {category.value: text for category, text in questions.category.criteria.items()},
    }
    return schema


def from_laya_answers(answers: Mapping[str, Mapping[str, Any]], questions: QuestionSet) -> Judgement:
    judgement: dict[Proposition, float] = {}
    for question in questions.yes_no:
        if question.key not in answers:
            raise KeyError(f"Laya returned no answer for {question.key}")
        judgement[question.proposition] = float(answers[question.key]["noul"])
    category = answers.get(questions.category.key)
    if category is None:
        raise KeyError(f"Laya returned no answer for {questions.category.key}")
    for value, probability in category["probabilities"].items():
        judgement[Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory(value))] = float(probability)
    return judgement


class LayaClassifier:
    """Runs the multilingual checkpoint (Berlin text is mixed German/English).

    `max_len=2048` lets a page passage of ~1,500 characters fit with the question heads; Laya's
    README reports stable accuracy well below 4,000 tokens.
    """

    def __init__(
        self,
        questions: QuestionSet = QUESTION_SET_V1,
        checkpoint: str = "multilingual",
        device: str | None = None,
        max_len: int = 2048,
        batch_size: int = 4,  # 4 x 2,048 tokens fits in ~3 GB RAM; raise it on bigger machines
    ) -> None:
        import laya  # optional dependency, imported only when the real model is wanted

        self._router = laya.Router(device=device, max_loaded=1, default=checkpoint)
        self._questions = questions
        self._schema = to_laya_schema(questions)
        self._checkpoint = checkpoint
        self._max_len = max_len
        self._batch_size = batch_size
        self._model_id = f"laya-{laya.__version__}-{checkpoint}"

    @property
    def model_id(self) -> str:
        return self._model_id

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        if not texts:
            return []
        requests = [
            {"state": text, "questions": self._schema, "model": self._checkpoint, "max_len": self._max_len}
            for text in texts
        ]
        results = self._router.predict_batch(requests, batch_size=self._batch_size)
        return [from_laya_answers(result["answers"], self._questions) for result in results]
