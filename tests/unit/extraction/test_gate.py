from __future__ import annotations

from collections.abc import Sequence

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.extraction.gate import LexicalGate
from pull_berlin.extraction.ports import Judgement

RENT = Proposition(ClaimType.IS_RENTABLE_FOR_PRIVATE_EVENTS)
HOSTS = Proposition(ClaimType.HOSTS_EVENING_EVENTS)
LATE = Proposition(ClaimType.OPERATES_PAST_MIDNIGHT)
CLUB = Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.CLUB)


class AlwaysYes:
    model_id = "yes"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        self.seen.extend(texts)
        return [{RENT: 1.0, HOSTS: 1.0, LATE: 1.0, CLUB: 0.9} for _ in texts]


def test_text_without_any_relevant_vocabulary_never_reaches_the_model() -> None:
    inner = AlwaysYes()
    (judgement,) = LexicalGate(inner).classify(["Pflegeberatung nach § 37 SGB XI und Alltagshilfe zu Hause."])
    assert inner.seen == []
    assert all(value == 0.0 for value in judgement.values())


def test_rental_vocabulary_lets_the_model_decide_rentability() -> None:
    (judgement,) = LexicalGate(AlwaysYes()).classify(["Unser Saal kann für Hochzeiten gemietet werden."])
    assert judgement[RENT] == 1.0


def test_propositions_whose_vocabulary_is_absent_are_silenced() -> None:
    (judgement,) = LexicalGate(AlwaysYes()).classify(["Unser Saal kann für Hochzeiten gemietet werden."])
    assert judgement[LATE] == 0.0


def test_late_hours_open_the_gate_for_operating_past_midnight() -> None:
    (judgement,) = LexicalGate(AlwaysYes()).classify(["Freitags Party bis 5 Uhr morgens im Club."])
    assert judgement[LATE] == 1.0


def test_category_judgement_passes_through_when_the_model_was_asked() -> None:
    (judgement,) = LexicalGate(AlwaysYes()).classify(["Clubnacht mit DJs, Party bis 6 Uhr."])
    assert judgement[CLUB] == 0.9


def test_only_gated_texts_are_sent_and_order_is_kept() -> None:
    inner = AlwaysYes()
    texts = [
        "Kaffee und Kuchen am Nachmittag.",
        "Location mieten für Firmenfeiern.",
        "Brot vom Bäcker nebenan.",
    ]
    judgements = LexicalGate(inner).classify(texts)
    assert inner.seen == ["Location mieten für Firmenfeiern."]
    assert [j[RENT] for j in judgements] == [0.0, 1.0, 0.0]


def test_model_id_names_the_gate() -> None:
    assert LexicalGate(AlwaysYes()).model_id == "gated-yes"
