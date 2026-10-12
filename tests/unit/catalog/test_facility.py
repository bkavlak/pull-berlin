from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.claim import ClaimType
from pull_berlin.catalog.domain.facility import ExternalRef, Facility
from pull_berlin.catalog.domain.values import GeoPoint, NotInBerlinError

from .builders import facility, observation, statement


class TestCreationFromObservation:
    def test_facility_is_identified_by_its_first_external_reference(self) -> None:
        assert facility(local_id="node/42").id == "osm:node/42"

    def test_facility_remembers_where_it_was_observed(self) -> None:
        assert facility(local_id="way/7").refs == frozenset({ExternalRef("osm", "way/7")})

    def test_facility_outside_berlin_cannot_be_created(self) -> None:
        with pytest.raises(NotInBerlinError):
            facility(location=GeoPoint(lat=48.137, lon=11.575))

    def test_statements_of_the_observation_become_the_facilitys_statements(self) -> None:
        s = statement(ClaimType.HOSTS_EVENING_EVENTS)
        assert facility(statements=(s,)).statements == (s,)

    def test_website_is_kept(self) -> None:
        assert facility(website="https://tresorberlin.com").websites == frozenset(
            {"https://tresorberlin.com"}
        )


class TestMerge:
    def test_merge_unions_references_and_never_drops_evidence(self) -> None:
        a = facility(local_id="node/1", statements=(statement(ClaimType.HOSTS_EVENING_EVENTS),))
        b = facility(local_id="way/2", statements=(statement(ClaimType.OPERATES_PAST_MIDNIGHT),))
        merged = a.merge(b)
        assert merged.refs == a.refs | b.refs
        assert set(merged.statements) == set(a.statements) | set(b.statements)

    def test_merge_is_symmetric_in_identity(self) -> None:
        a, b = facility(local_id="node/1"), facility(local_id="way/2")
        assert a.merge(b).id == b.merge(a).id

    def test_merge_keeps_the_most_descriptive_name(self) -> None:
        a = facility(local_id="node/1", name="Tresor")
        b = facility(local_id="way/2", name="Tresor Berlin Club")
        assert a.merge(b).name.display == "Tresor Berlin Club"


class TestOntology:
    def test_facility_is_a_cco_material_artifact(self) -> None:
        assert Facility.ONTOLOGY_TERM == "https://www.commoncoreontologies.org/ont00000995"

    def test_observation_has_an_ontology_term(self) -> None:
        assert observation().ONTOLOGY_TERM.endswith("/Observation")
