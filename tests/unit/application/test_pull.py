from __future__ import annotations

import pytest

from pull_berlin.application.pull import pull
from pull_berlin.sources.osm_overpass import ENDPOINT, OsmOverpassSource
from pull_berlin.sourcing.ports import FetchError

from ...fakes import FakeFetcher, osm_node, overpass_json

CLUB = osm_node(1, "Tresor", 52.5106, 13.4199, amenity="nightclub", opening_hours="Fr,Sa 23:59+")
CLUB_BUILDING = {
    "type": "way",
    "id": 2,
    "center": {"lat": 52.5108, "lon": 13.4201},
    "tags": {"name": "Tresor Berlin", "amenity": "nightclub"},
}
HALL = osm_node(3, "Festsaal Kreuzberg", 52.4975, 13.4489, amenity="events_venue")
CAFE_BAR = osm_node(
    4, "Tagescafé", 52.53, 13.40, amenity="community_centre", opening_hours="Mo-Fr 09:00-15:00"
)
IN_POTSDAM = osm_node(5, "Waschhaus", 52.4010, 13.0450, amenity="nightclub")


def run(*elements: dict[str, object], include_all: bool = False):  # type: ignore[no-untyped-def]
    fetcher = FakeFetcher({ENDPOINT: overpass_json(*elements)})
    return pull([OsmOverpassSource()], fetcher, include_all=include_all)


def test_the_same_club_mapped_as_node_and_building_becomes_one_facility() -> None:
    result = run(CLUB, CLUB_BUILDING)
    assert [f.name for f in result.facilities] == ["Tresor Berlin"]


def test_facility_lists_every_source_reference() -> None:
    (club,) = run(CLUB, CLUB_BUILDING).facilities
    assert club.refs == ("osm:node/1", "osm:way/2")


def test_observations_outside_berlin_are_rejected_and_counted() -> None:
    result = run(CLUB, IN_POTSDAM)
    assert result.report.outside_berlin == 1
    assert [f.name for f in result.facilities] == ["Tresor"]


def test_by_default_only_facilities_with_an_evening_or_night_offering_are_kept() -> None:
    result = run(HALL, CAFE_BAR)
    assert [f.name for f in result.facilities] == ["Festsaal Kreuzberg"]


def test_include_all_keeps_facilities_without_offerings() -> None:
    result = run(HALL, CAFE_BAR, include_all=True)
    assert {f.name for f in result.facilities} == {"Festsaal Kreuzberg", "Tagescafé"}


def test_report_counts_each_stage() -> None:
    report = run(CLUB, CLUB_BUILDING, HALL, CAFE_BAR, IN_POTSDAM).report
    assert (report.observations, report.outside_berlin, report.facilities, report.in_scope) == (5, 1, 3, 2)


def test_report_counts_observations_per_source() -> None:
    assert run(CLUB, HALL).report.observations_per_source == {"osm": 2}


def test_club_view_shows_hosting_offering_in_evening_and_night() -> None:
    (club,) = run(CLUB).facilities
    (offering,) = club.offerings
    assert (offering.kind, offering.windows) == ("event_hosting", ("evening", "night"))


def test_views_are_sorted_by_id_for_reproducible_exports() -> None:
    ids = [f.id for f in run(HALL, CLUB).facilities]
    assert ids == sorted(ids)


def test_a_source_that_cannot_be_fetched_fails_the_run_loudly() -> None:
    with pytest.raises(FetchError):
        pull([OsmOverpassSource()], FakeFetcher({}))


class TestEnrichmentFromVenueSites:
    SITE = "https://bar.example/"
    BAR = osm_node(10, "Bar Zentral", 52.52, 13.41, amenity="bar", website="https://bar.example/")

    def run(self, pages: dict[str, str]):  # type: ignore[no-untyped-def]
        from pull_berlin.extraction.keyword_classifier import KeywordClassifier
        from pull_berlin.sources.venue_site import VenueSiteSource

        fetcher = FakeFetcher({ENDPOINT: overpass_json(self.BAR), **pages})
        return pull(
            [OsmOverpassSource()], fetcher, enrichers=[VenueSiteSource()], classifier=KeywordClassifier()
        )

    def test_rental_page_on_the_venue_site_brings_a_bar_into_scope_as_hireable(self) -> None:
        home = "<html><body><p>Bar Zentral in Mitte. Unsere Bar kann für private Feiern gemietet werden.</p>"
        (bar,) = self.run({self.SITE: home}).facilities
        assert [o.kind for o in bar.offerings] == ["event_hire"]
        assert "site:bar.example" in bar.refs

    def test_site_without_signal_leaves_the_bar_out_of_scope(self) -> None:
        home = "<html><body><p>Bar Zentral in Mitte. Cocktails, Wein und Bier seit 1998 in bester Lage.</p>"
        assert self.run({self.SITE: home}).facilities == []

    def test_report_counts_visited_sites_and_classified_passages(self) -> None:
        home = "<html><body><p>Bar Zentral in Mitte. Cocktails, Wein und Bier seit 1998 in bester Lage.</p>"
        report = self.run({self.SITE: home}).report
        assert (report.sites_attempted, report.sites_observed, report.passages_classified) == (1, 1, 1)

    def test_unreachable_site_is_counted_not_fatal(self) -> None:
        report = self.run({}).report
        assert (report.sites_attempted, report.sites_observed) == (1, 0)


class TestEnrichingOnlySomeCategories:
    def test_site_categories_limit_website_visits_to_those_kinds_of_place(self) -> None:
        from pull_berlin.catalog.domain.values import SpaceCategory
        from pull_berlin.extraction.keyword_classifier import KeywordClassifier
        from pull_berlin.sources.venue_site import VenueSiteSource

        bar = osm_node(20, "Bar Eins", 52.52, 13.41, amenity="bar", website="https://bar.example/")
        club = osm_node(21, "Club Zwei", 52.50, 13.45, amenity="nightclub", website="https://club.example/")
        fetcher = FakeFetcher({ENDPOINT: overpass_json(bar, club)})
        pull(
            [OsmOverpassSource()],
            fetcher,
            enrichers=[VenueSiteSource()],
            classifier=KeywordClassifier(),
            enrich_categories={SpaceCategory.BAR},
        )
        visited = {r.url.split("/")[2] for r in fetcher.requests if r.source_id == "site"}
        assert visited == {"bar.example"}


class TestParallelEnrichment:
    def test_parallel_site_visits_give_the_same_catalog_as_sequential_ones(self) -> None:
        from pull_berlin.extraction.keyword_classifier import KeywordClassifier
        from pull_berlin.sources.venue_site import VenueSiteSource

        bars = [
            osm_node(
                30 + i, f"Bar {i}", 52.50 + i * 0.01, 13.40, amenity="bar", website=f"https://bar{i}.example/"
            )
            for i in range(6)
        ]
        pages = {
            f"https://bar{i}.example/": f"<p>Bar {i}: das Hinterzimmer ist für private Feiern mietbar.</p>"
            for i in range(0, 6, 2)
        }

        def run(workers: int) -> list[tuple[str, tuple[str, ...]]]:
            fetcher = FakeFetcher({ENDPOINT: overpass_json(*bars), **pages})
            result = pull(
                [OsmOverpassSource()],
                fetcher,
                enrichers=[VenueSiteSource()],
                classifier=KeywordClassifier(),
                include_all=True,
                enrich_workers=workers,
            )
            return [(f.id, tuple(o.kind for o in f.offerings)) for f in result.facilities]

        assert run(workers=4) == run(workers=1)
