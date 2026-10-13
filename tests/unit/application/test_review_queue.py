from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from pull_berlin.application.review import ReviewItem, choose_next, find, prepare
from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.observation import Observation, Passage
from pull_berlin.extraction.ports import Judgement
from pull_berlin.review.domain import Review, Verdict
from pull_berlin.shared_kernel import SourceKind
from pull_berlin.sourcing.domain import Source
from pull_berlin.sourcing.ports import Fetcher

from ...fakes import FakeFetcher
from ..catalog.builders import facility, statement

RENT = ClaimType.IS_RENTABLE_FOR_PRIVATE_EVENTS
HOSTS = ClaimType.HOSTS_EVENING_EVENTS
SURE = facility(
    local_id="node/1", name="Sure Hall", website="https://sure.example", statements=(statement(RENT),)
)
UNSURE = facility(
    local_id="node/2",
    name="Café Grenzfall",
    website="https://grenzfall.example",
    statements=(statement(RENT, source_id="site", kind=SourceKind.VENUE_OWN_SITE, strength=0.62),),
)
NO_SITE = facility(local_id="node/3", name="Kiezraum", statements=(statement(RENT, strength=0.75),))


class StubSite:
    """An enricher that 'reads' two passages from any website."""

    source = Source("site", SourceKind.VENUE_OWN_SITE, "stub")

    def observe(self, facility: Facility, fetcher: Fetcher) -> Observation | None:
        return Observation(
            "site",
            SourceKind.VENUE_OWN_SITE,
            "grenzfall.example",
            "https://grenzfall.example/",
            facility.name,
            facility.location,
            passages=(
                Passage("Wir zeigen Filme am Abend.", "https://grenzfall.example/"),
                Passage("Unseren Saal mieten für Feiern.", "https://grenzfall.example/mieten"),
            ),
        )


class StubClassifier:
    model_id = "stub-1"

    def classify(self, texts: Sequence[str]) -> list[Judgement]:
        return [{Proposition(RENT): 0.9 if "mieten" in t else 0.1, Proposition(HOSTS): 0.0} for t in texts]


def said(facility_id: str) -> Review:
    return Review("ada", facility_id, "", date(2026, 10, 13), {RENT: Verdict.YES})


def test_next_is_the_facility_closest_to_the_threshold() -> None:
    assert choose_next([SURE, UNSURE], []) == UNSURE


def test_reviewed_and_skipped_facilities_are_not_offered_again() -> None:
    assert choose_next([SURE, UNSURE], [said(UNSURE.id)]) == SURE
    assert choose_next([SURE, UNSURE], [], skipped={UNSURE.id}) == SURE


def test_facilities_without_a_website_are_not_queued() -> None:
    assert choose_next([NO_SITE], []) is None


def test_find_by_id_or_by_name_ignoring_accents() -> None:
    assert find([SURE, UNSURE], "osm:node/1") == [SURE]
    assert find([SURE, UNSURE], "cafe grenz") == [UNSURE]


def test_item_shows_the_passage_the_model_rated_highest() -> None:
    item = prepare(UNSURE, StubSite(), FakeFetcher({}), StubClassifier())
    rent = next(c for c in item.checks if c.claim_type is RENT)
    assert rent.shown is not None
    assert rent.shown.url == "https://grenzfall.example/mieten"
    assert rent.shown.probability == 0.9
    assert item.model == "stub-1"
    assert item.pages_read == 2


def test_item_shows_what_the_catalog_believes_and_why() -> None:
    rent = next(c for c in prepare(UNSURE, None, None, None).checks if c.claim_type is RENT)
    assert rent.catalog_confidence == 0.589
    assert rent.sources == ("site: yes",)
    assert rent.shown is None


def test_a_claim_the_model_finds_nowhere_shows_no_passage() -> None:
    item = prepare(UNSURE, StubSite(), FakeFetcher({}), StubClassifier())
    assert next(c for c in item.checks if c.claim_type is HOSTS).shown is None


def test_item_links_to_openstreetmap_and_the_website() -> None:
    assert prepare(UNSURE, None, None, None).links == (
        "https://www.openstreetmap.org/node/2",
        "https://grenzfall.example",
    )


def test_item_survives_being_saved_between_showing_and_recording() -> None:
    item = prepare(UNSURE, StubSite(), FakeFetcher({}), StubClassifier())
    assert ReviewItem.from_dict(item.to_dict()) == item


def test_answers_become_a_review_keeping_what_was_shown() -> None:
    item = prepare(UNSURE, StubSite(), FakeFetcher({}), StubClassifier())
    made = item.review("ada", {"rentable": Verdict.YES, "hosts": Verdict.NO}, date(2026, 10, 13), "saw it")
    assert made.facility_name == "Café Grenzfall"
    assert made.model == "stub-1"
    assert set(made.shown) == {RENT}
    assert made.note == "saw it"


def test_passages_behind_an_unsure_answer_are_not_kept() -> None:
    item = prepare(UNSURE, StubSite(), FakeFetcher({}), StubClassifier())
    made = item.review("ada", {"rentable": Verdict.UNSURE, "hosts": Verdict.NO}, date(2026, 10, 13))
    assert made.shown == {}
