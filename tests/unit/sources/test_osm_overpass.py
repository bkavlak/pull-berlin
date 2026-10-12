from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from pull_berlin.catalog.domain.claim import ClaimType, Proposition, Stance
from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.shared_kernel import SourceKind
from pull_berlin.sources.osm_overpass import OsmOverpassSource
from pull_berlin.sourcing.domain import RawDocument

SOURCE = OsmOverpassSource()


def document(*elements: dict[str, object]) -> RawDocument:
    return RawDocument(
        source_id="osm",
        url="https://overpass-api.de/api/interpreter",
        content=json.dumps({"elements": list(elements)}),
        fetched_at=datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc),
    )


def node(id_: int = 1, **tags: str) -> dict[str, object]:
    return {"type": "node", "id": id_, "lat": 52.5113, "lon": 13.4106, "tags": {"name": "Beispiel", **tags}}


def query() -> str:
    (request,) = SOURCE.requests()
    return dict(request.form)["data"]


def propositions(observation_statements: object) -> set[Proposition]:
    return {s.proposition for s in observation_statements}  # type: ignore[attr-defined]


class TestRequest:
    def test_source_is_open_geodata(self) -> None:
        assert SOURCE.source.kind is SourceKind.OPEN_GEODATA

    def test_single_post_request_sends_the_query_as_overpass_data_field(self) -> None:
        (request,) = SOURCE.requests()
        assert request.method == "POST"
        assert set(dict(request.form)) == {"data"}

    def test_query_is_restricted_to_the_berlin_boundary(self) -> None:
        assert '"name"="Berlin"' in query() and '"admin_level"="4"' in query()

    def test_query_asks_for_every_mapped_amenity(self) -> None:
        for amenity in ("nightclub", "bar", "pub", "events_venue", "music_venue", "community_centre"):
            assert amenity in query()

    def test_query_returns_centres_so_ways_have_a_location(self) -> None:
        assert "out center tags" in query()


class TestParse:
    def test_named_node_becomes_an_observation_with_its_osm_identity(self) -> None:
        (obs,) = SOURCE.parse(document(node(42, amenity="bar")))
        assert (obs.source_id, obs.local_id) == ("osm", "node/42")
        assert obs.url == "https://www.openstreetmap.org/node/42"

    def test_way_uses_its_centre_as_location(self) -> None:
        way = {
            "type": "way",
            "id": 7,
            "center": {"lat": 52.5, "lon": 13.4},
            "tags": {"name": "W", "amenity": "pub"},
        }
        (obs,) = SOURCE.parse(document(way))
        assert (obs.location.lat, obs.location.lon) == (52.5, 13.4)

    def test_unnamed_elements_are_skipped_because_a_space_must_be_designated(self) -> None:
        unnamed = {"type": "node", "id": 3, "lat": 52.5, "lon": 13.4, "tags": {"amenity": "bar"}}
        assert SOURCE.parse(document(unnamed)) == []

    def test_elements_without_coordinates_are_skipped(self) -> None:
        nowhere = {"type": "relation", "id": 9, "tags": {"name": "X", "amenity": "theatre"}}
        assert SOURCE.parse(document(nowhere)) == []

    def test_nightclub_hosts_evening_events_and_is_a_club(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="nightclub")))
        assert {
            Proposition(ClaimType.HOSTS_EVENING_EVENTS),
            Proposition(ClaimType.FALLS_UNDER_CATEGORY, SpaceCategory.CLUB),
        } <= propositions(obs.statements)

    def test_events_venue_is_hireable(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="events_venue")))
        assert Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS) in propositions(obs.statements)

    def test_tag_evidence_quotes_the_tag(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="events_venue")))
        assert {s.evidence.excerpt for s in obs.statements} == {"amenity=events_venue"}

    def test_late_opening_hours_support_operating_past_midnight(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="bar", opening_hours="Mo-Su 19:00-03:00")))
        night = [s for s in obs.statements if s.proposition == Proposition(ClaimType.OPERATES_PAST_MIDNIGHT)]
        assert [(s.evidence.stance, s.evidence.excerpt) for s in night] == [
            (Stance.SUPPORTS, "opening_hours=Mo-Su 19:00-03:00")
        ]

    def test_daytime_opening_hours_oppose_evening_and_night_operation(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="community_centre", opening_hours="Mo-Fr 09:00-16:00")))
        opposed = {s.proposition.claim_type for s in obs.statements if s.evidence.stance is Stance.OPPOSES}
        assert opposed == {ClaimType.OPERATES_IN_EVENING, ClaimType.OPERATES_PAST_MIDNIGHT}

    def test_unparseable_opening_hours_say_nothing(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="bar", opening_hours="by appointment")))
        assert all(not s.evidence.excerpt.startswith("opening_hours") for s in obs.statements)

    def test_website_falls_back_to_contact_website(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="bar", **{"contact:website": "https://x.example"})))
        assert obs.website == "https://x.example"

    def test_unmapped_amenity_still_observed_without_statements(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="bench")))
        assert obs.statements == ()

    def test_malformed_document_raises_a_clear_error(self) -> None:
        bad = RawDocument(
            "osm", "https://overpass-api.de", "<html>rate limited</html>", document().fetched_at
        )
        with pytest.raises(ValueError, match="Overpass"):
            SOURCE.parse(bad)


class TestBarEventTags:
    HOSTS = Proposition(ClaimType.HOSTS_EVENING_EVENTS)

    @pytest.mark.parametrize(
        "tags",
        [{"live_music": "yes"}, {"karaoke": "yes"}, {"nightclub": "yes"}, {"music_genre": "jazz"}],
    )
    def test_event_tags_on_a_bar_say_it_hosts_evening_events(self, tags: dict[str, str]) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="bar", **tags)))
        assert self.HOSTS in propositions(obs.statements)

    def test_live_music_no_says_nothing_about_hosting(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="bar", live_music="no")))
        assert self.HOSTS not in propositions(obs.statements)

    def test_event_tag_evidence_quotes_the_tag(self) -> None:
        (obs,) = SOURCE.parse(document(node(amenity="pub", live_music="yes")))
        hosting = [s for s in obs.statements if s.proposition == self.HOSTS]
        assert [s.evidence.excerpt for s in hosting] == ["live_music=yes"]

    def test_a_bar_with_live_music_and_late_hours_is_hosting_at_night(self) -> None:
        from pull_berlin.catalog.domain.assessment import AssessmentPolicy
        from pull_berlin.catalog.domain.offering import OfferingKind
        from pull_berlin.catalog.domain.values import TimeWindow

        (obs,) = SOURCE.parse(
            document(node(amenity="bar", live_music="yes", opening_hours="Fr,Sa 20:00-04:00"))
        )
        (offering,) = AssessmentPolicy().assess(obs.statements).offerings
        assert offering.kind is OfferingKind.EVENT_HOSTING
        assert offering.windows == frozenset({TimeWindow.EVENING, TimeWindow.NIGHT})
