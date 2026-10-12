from __future__ import annotations

import contextlib
from collections.abc import Sequence
from pathlib import Path

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.extraction.caching_classifier import CachingClassifier
from pull_berlin.extraction.ports import Judgement

HIRE = Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)
LOFT = Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.LOFT)


class CountingClassifier:
    model_id = "counting"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        self.seen.extend(texts)
        return [{HIRE: 0.8, LOFT: 0.6} for _ in texts]


def test_each_text_is_classified_once_across_runs(tmp_path: Path) -> None:
    inner = CountingClassifier()
    CachingClassifier(inner, tmp_path / "c.jsonl", "v1").classify(["a", "b"])
    judgements = CachingClassifier(inner, tmp_path / "c.jsonl", "v1").classify(["b", "a", "c"])
    assert inner.seen == ["a", "b", "c"]
    assert judgements[0] == {HIRE: 0.8, LOFT: 0.6}


def test_new_question_version_invalidates_cached_answers(tmp_path: Path) -> None:
    inner = CountingClassifier()
    CachingClassifier(inner, tmp_path / "c.jsonl", "v1").classify(["a"])
    CachingClassifier(inner, tmp_path / "c.jsonl", "v2").classify(["a"])
    assert inner.seen == ["a", "a"]


def test_cache_keeps_the_inner_model_id(tmp_path: Path) -> None:
    assert CachingClassifier(CountingClassifier(), tmp_path / "c.jsonl", "v1").model_id == "counting"


class FailingAfter(CountingClassifier):
    def __init__(self, allowed: int) -> None:
        super().__init__()
        self.allowed = allowed

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        if len(self.seen) + len(texts) > self.allowed:
            raise RuntimeError("interrupted")
        return super().classify(texts)


def test_progress_is_kept_when_a_long_batch_is_interrupted(tmp_path: Path) -> None:
    texts = [f"text {i}" for i in range(20)]
    with contextlib.suppress(RuntimeError):
        CachingClassifier(FailingAfter(allowed=16), tmp_path / "c.jsonl", "v1", chunk_size=8).classify(texts)
    resumed = CountingClassifier()
    CachingClassifier(resumed, tmp_path / "c.jsonl", "v1", chunk_size=8).classify(texts)
    assert resumed.seen == texts[16:]
