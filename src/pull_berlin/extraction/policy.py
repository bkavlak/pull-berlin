"""Turns classifier judgements into catalog statements.

A text that does not mention renting is not evidence against renting, so low probabilities are
silence, never opposition. Opposition comes only from explicit facts (e.g. known opening hours).
"""

from __future__ import annotations

from collections.abc import Sequence

from pull_berlin.catalog.domain.claim import ClaimType, Evidence, Proposition, Statement
from pull_berlin.catalog.domain.observation import Passage
from pull_berlin.extraction.ports import Judgement
from pull_berlin.shared_kernel import SourceKind

_EXCERPT_CHARS = 280


class ExtractionPolicy:
    def __init__(self, min_support: float = 0.5) -> None:
        self.min_support = min_support

    def statements(
        self,
        passages: Sequence[Passage],
        judgements: Sequence[Judgement],
        source_id: str,
        source_kind: SourceKind,
    ) -> tuple[Statement, ...]:
        if len(passages) != len(judgements):
            raise ValueError(f"{len(passages)} passages but {len(judgements)} judgements")
        result: list[Statement] = []
        for passage, judgement in zip(passages, judgements, strict=True):
            for proposition, probability in self._supported(judgement):
                evidence = Evidence(
                    source_id=source_id,
                    source_kind=source_kind,
                    url=passage.url,
                    excerpt=_excerpt(passage.text),
                    strength=round(probability, 4),
                )
                result.append(Statement(proposition, evidence))
        return tuple(result)

    def _supported(self, judgement: Judgement) -> list[tuple[Proposition, float]]:
        yes_no = [
            (p, prob)
            for p, prob in judgement.items()
            if p.claim_type is not ClaimType.FALLS_UNDER_CATEGORY and prob >= self.min_support
        ]
        categories = [
            (p, prob) for p, prob in judgement.items() if p.claim_type is ClaimType.FALLS_UNDER_CATEGORY
        ]
        best = max(categories, key=lambda item: item[1], default=None)
        if best is not None and best[1] >= self.min_support:
            yes_no.append(best)
        return yes_no


def _excerpt(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _EXCERPT_CHARS else text[:_EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"
