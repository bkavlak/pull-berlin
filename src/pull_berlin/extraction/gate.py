"""Lexical gate in front of a model classifier.

Measured on Berlin venue sites (2026-10-12): zero-shot Laya says "rentable" with p=1.0 for pages
about home care or travel agencies. A text can only *say* that a place is for rent if it uses
some rental vocabulary, so the gate asks the model about a proposition only when such vocabulary is
present, and stays silent (0.0) otherwise. The patterns are deliberately broad: they decide
whether to ask, the model decides the answer. Texts that open no gate are never sent at all.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.extraction.ports import Judgement, TextClassifier

DEFAULT_GATES: Mapping[Proposition, re.Pattern[str]] = {
    Proposition(ClaimType.IS_RENTABLE_FOR_PRIVATE_EVENTS): re.compile(
        r"miet|vermiet|buch|anfrage|feier|hochzeit|geburtstag|event|location|r[aä]um|saal|halle|privat|"
        r"exklusiv|\bhire|\brent|\bbook|venue|kapazit|personen|g[aä]ste",
        re.IGNORECASE,
    ),
    Proposition(ClaimType.HOSTS_EVENING_EVENTS): re.compile(
        r"konzert|party|parties|club|lesung|theater|kino|programm|veranstalt|event|live|\bdj|ausstellung|"
        r"vernissage|ticket|festival|show|performance|b[uü]hne|stage",
        re.IGNORECASE,
    ),
    Proposition(ClaimType.OPERATES_PAST_MIDNIGHT): re.compile(
        r"\d{1,2}[:.]\d{2}|\d{1,2}\s?uhr|nacht|night|open ?end|\blate\b|morgens|sunrise|afterhour",
        re.IGNORECASE,
    ),
}


class LexicalGate:
    def __init__(
        self, inner: TextClassifier, gates: Mapping[Proposition, re.Pattern[str]] = DEFAULT_GATES
    ) -> None:
        self._inner = inner
        self._gates = gates

    @property
    def model_id(self) -> str:
        return f"gated-{self._inner.model_id}"

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        open_gates = [{p for p, pattern in self._gates.items() if pattern.search(text)} for text in texts]
        asked = [i for i, gates in enumerate(open_gates) if gates]
        answers = dict(zip(asked, self._inner.classify([texts[i] for i in asked]), strict=True))

        judgements: list[Judgement] = []
        for i, gates in enumerate(open_gates):
            silent = {p: 0.0 for p in self._gates}
            if i not in answers:
                judgements.append(silent)
                continue
            judgement = dict(answers[i])
            for proposition in self._gates:
                if proposition not in gates:
                    judgement[proposition] = 0.0
            judgements.append(judgement)
        return judgements
