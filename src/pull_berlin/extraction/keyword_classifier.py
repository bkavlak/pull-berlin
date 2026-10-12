"""Deterministic baseline classifier (German + English keywords).

Two jobs: a floor that Laya must beat in evaluation, and a model-free classifier so the pipeline
and its e2e test run without PyTorch.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.extraction.ports import Judgement

_SIGNAL = 0.9
_PATTERNS = {
    Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS): re.compile(
        r"\w*miet\w*|vermiet|firmenfeier|weihnachtsfeier|hochzeit|private[nrs]? (feier|event|party)|"
        r"private hire|for hire|venue hire|rent (our|the|a)|exklusiv buchen|location buchen|raum buchen",
        re.IGNORECASE,
    ),
    Proposition(ClaimType.HOSTS_EVENING_EVENTS): re.compile(
        r"konzert|club ?night|clubnacht|lesung|theater|live ?musik|programm|line ?up|tickets?\b|"
        r"veranstaltungskalender|upcoming events|party|parties",
        re.IGNORECASE,
    ),
    Proposition(ClaimType.OPERATES_PAST_MIDNIGHT): re.compile(
        r"bis \d{1,2} uhr morgens|bis in den morgen|bis in die früh|open ?end|afterhour|"
        r"open (till|until) late|till (sunrise|morning)|bis (0?[1-8])(:00)? uhr",
        re.IGNORECASE,
    ),
}


class KeywordClassifier:
    model_id = "keywords-v1"

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        return [
            {
                proposition: (_SIGNAL if pattern.search(text) else 0.0)
                for proposition, pattern in _PATTERNS.items()
            }
            for text in texts
        ]
