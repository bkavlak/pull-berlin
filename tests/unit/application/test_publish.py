from __future__ import annotations

from datetime import date

from pull_berlin.application.publish import changes, describe, publish
from pull_berlin.catalog.domain.claim import ClaimType
from pull_berlin.publishing.renderers import render_geojson, render_json
from pull_berlin.publishing.snapshot import read_snapshot
from pull_berlin.review.domain import Review, Verdict
from pull_berlin.shared_kernel import SourceKind

from ..catalog.builders import facility, statement

HIRE = ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS
HALL = facility(
    local_id="node/1",
    name="Festsaal",
    statements=(statement(HIRE, excerpt="amenity=events_venue"), statement(ClaimType.OPERATES_IN_EVENING)),
)
BAR = facility(local_id="node/2", name="Eckkneipe", statements=(statement(ClaimType.OPERATES_IN_EVENING),))


def said(facility_id: str, verdict: Verdict, reviewer: str = "ada") -> Review:
    return Review(reviewer, facility_id, "", date(2026, 10, 13), {HIRE: verdict})


def test_without_reviews_publishing_shows_what_the_sources_say() -> None:
    result = publish([HALL, BAR], [])
    assert [v.name for v in result.facilities] == ["Festsaal"]
    assert result.reviewed == 0


def test_a_review_changes_what_is_published() -> None:
    result = publish([HALL, BAR], [said("osm:node/1", Verdict.NO), said("osm:node/2", Verdict.YES)])
    assert [v.name for v in result.facilities] == ["Eckkneipe"]
    assert result.reviewed == 2


def test_published_facilities_name_their_reviewers() -> None:
    (view,) = publish(
        [HALL], [said("osm:node/1", Verdict.YES, "grace"), said("osm:node/1", Verdict.YES)]
    ).facilities
    assert view.reviewers == ("ada", "grace")


def test_reviews_of_facilities_missing_from_the_snapshot_are_reported() -> None:
    stray = said("osm:node/999", Verdict.YES)
    assert publish([HALL], [stray]).unknown == [stray]


def test_snapshot_round_trip_reproduces_the_catalog() -> None:
    site = statement(
        HIRE, source_id="site", kind=SourceKind.VENUE_OWN_SITE, strength=0.9, url="https://h.example/"
    )
    views = publish([HALL.with_statements((site,))], [said("osm:node/1", Verdict.YES)]).facilities
    again = publish(read_snapshot(render_json(views)), []).facilities
    assert again == views


def test_map_data_carries_who_reviewed_a_facility() -> None:
    views = publish([HALL], [said("osm:node/1", Verdict.YES)]).facilities
    assert '"reviewed_by": "ada"' in render_geojson(views)


def test_changes_list_facilities_that_appear_disappear_or_change() -> None:
    before = publish([HALL, BAR], []).facilities
    after = publish([HALL, BAR], [said("osm:node/1", Verdict.NO), said("osm:node/2", Verdict.YES)]).facilities
    assert [
        (c.name, c.before == "not on the map", c.after == "not on the map") for c in changes(before, after)
    ] == [
        ("Festsaal", False, True),
        ("Eckkneipe", True, False),
    ]


def test_unchanged_facilities_are_not_listed_as_changes() -> None:
    views = publish([HALL], []).facilities
    assert changes(views, views) == []


def test_description_names_offering_confidence_and_time_windows() -> None:
    (view,) = publish([HALL], []).facilities
    assert describe(view) == "event_hire 0.80 (evening)"
