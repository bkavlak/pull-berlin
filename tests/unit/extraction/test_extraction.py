from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.claim import ClaimType, Proposition, Stance
from pull_berlin.catalog.domain.observation import Passage
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.extraction.keyword_classifier import KeywordClassifier
from pull_berlin.extraction.policy import ExtractionPolicy
from pull_berlin.extraction.questions import QUESTION_SET_V1
from pull_berlin.shared_kernel import SourceKind

HIRE = Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS)
HOSTS = Proposition(ClaimType.HOSTS_EVENING_EVENTS)
LATE = Proposition(ClaimType.OPERATES_PAST_MIDNIGHT)
CLUB = Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.CLUB)
LOFT = Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.LOFT)

PASSAGE = Passage(
    text="Unsere Location kann für private Feiern gemietet werden.", url="https://x.example/mieten"
)
POLICY = ExtractionPolicy(min_support=0.5)


def extract(judgement: dict[Proposition, float]):  # type: ignore[no-untyped-def]
    return POLICY.statements([PASSAGE], [judgement], source_id="site", source_kind=SourceKind.VENUE_OWN_SITE)


class TestQuestionSet:
    def test_asks_one_yes_no_question_per_offering_relevant_claim(self) -> None:
        assert {q.proposition for q in QUESTION_SET_V1.yes_no} == {HIRE, HOSTS, LATE}

    def test_category_question_offers_every_category_with_a_prototype(self) -> None:
        assert set(QUESTION_SET_V1.category.criteria) == set(SpaceCategory)
        assert all(len(text) > 20 for text in QUESTION_SET_V1.category.criteria.values())

    def test_question_set_is_versioned_so_cached_answers_can_be_invalidated(self) -> None:
        assert QUESTION_SET_V1.version == "v1"


class TestExtractionPolicy:
    def test_confident_yes_becomes_supporting_evidence_with_the_probability_as_strength(self) -> None:
        (statement,) = extract({HIRE: 0.83})
        assert statement.proposition == HIRE
        assert (statement.evidence.stance, statement.evidence.strength) == (Stance.SUPPORTS, 0.83)

    def test_low_probability_is_silence_not_opposition(self) -> None:
        assert extract({HIRE: 0.1}) == ()

    def test_evidence_points_to_the_page_and_quotes_the_passage(self) -> None:
        (statement,) = extract({HIRE: 0.9})
        assert statement.evidence.url == "https://x.example/mieten"
        assert statement.evidence.excerpt.startswith("Unsere Location")

    def test_long_passages_are_quoted_shortened(self) -> None:
        long = Passage(text="Wort " * 200, url="https://x.example")
        (statement,) = POLICY.statements([long], [{HIRE: 0.9}], "site", SourceKind.VENUE_OWN_SITE)
        assert len(statement.evidence.excerpt) <= 281

    def test_only_the_most_likely_category_is_kept(self) -> None:
        statements = extract({CLUB: 0.7, LOFT: 0.2})
        assert [s.proposition for s in statements] == [CLUB]

    def test_uncertain_category_is_dropped(self) -> None:
        assert extract({CLUB: 0.4, LOFT: 0.35}) == ()

    def test_passages_and_judgements_must_line_up(self) -> None:
        with pytest.raises(ValueError):
            POLICY.statements([PASSAGE], [], "site", SourceKind.VENUE_OWN_SITE)


class TestKeywordClassifier:
    @pytest.mark.parametrize(
        "text",
        [
            "Die Räume können für Firmenfeiern gemietet werden.",
            "Location mieten für Ihre Hochzeit",
            "Our venue is available for private hire.",
            "Raumvermietung: Anfragen an info@x.de",
        ],
    )
    def test_rental_wording_signals_hireability(self, text: str) -> None:
        (judgement,) = KeywordClassifier().classify([text])
        assert judgement[HIRE] > 0.5

    def test_ordinary_text_signals_nothing(self) -> None:
        (judgement,) = KeywordClassifier().classify(["Wir haben Kaffee und Kuchen."])
        assert all(p == 0.0 for p in judgement.values())

    def test_late_closing_signals_operation_past_midnight(self) -> None:
        (judgement,) = KeywordClassifier().classify(["Party bis 5 Uhr morgens, open till late"])
        assert judgement[LATE] > 0.5

    def test_one_judgement_per_text(self) -> None:
        assert len(KeywordClassifier().classify(["a", "b", "c"])) == 3
