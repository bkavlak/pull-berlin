from __future__ import annotations

from pull_berlin.catalog.domain.resolution import ResolutionPolicy
from pull_berlin.catalog.domain.values import GeoPoint

from .builders import KREUZBERG, facility

POLICY = ResolutionPolicy(max_distance_m=75, min_name_similarity=0.85)
NEARBY = GeoPoint(lat=KREUZBERG.lat + 0.0003, lon=KREUZBERG.lon)  # ~33 m north
FAR = GeoPoint(lat=KREUZBERG.lat + 0.01, lon=KREUZBERG.lon)  # ~1.1 km north


def test_same_name_close_together_is_one_facility() -> None:
    resolved = POLICY.resolve([facility(local_id="node/1"), facility(local_id="way/2", location=NEARBY)])
    assert len(resolved) == 1


def test_same_name_far_apart_are_two_facilities() -> None:
    resolved = POLICY.resolve([facility(local_id="node/1"), facility(local_id="way/2", location=FAR)])
    assert len(resolved) == 2


def test_different_names_close_together_are_two_facilities() -> None:
    resolved = POLICY.resolve(
        [
            facility(local_id="node/1", name="Berghain"),
            facility(local_id="node/2", name="Kantine", location=NEARBY),
        ]
    )
    assert len(resolved) == 2


def test_resolution_is_transitive_across_a_chain() -> None:
    step = 0.0005  # ~55 m
    chain = [
        facility(local_id=f"node/{i}", location=GeoPoint(lat=KREUZBERG.lat + i * step, lon=KREUZBERG.lon))
        for i in range(3)
    ]
    assert len(POLICY.resolve(chain)) == 1


def test_resolved_facility_carries_all_references() -> None:
    (merged,) = POLICY.resolve([facility(local_id="node/1"), facility(local_id="way/2", location=NEARBY)])
    assert {ref.local_id for ref in merged.refs} == {"node/1", "way/2"}


def test_same_external_reference_is_one_facility_regardless_of_name() -> None:
    a = facility(local_id="node/1", name="Old Name")
    b = facility(local_id="node/1", name="Completely Different", location=FAR)
    assert len(POLICY.resolve([a, b])) == 1


def test_resolution_output_is_ordered_by_id_for_reproducible_exports() -> None:
    resolved = POLICY.resolve([facility(local_id="node/9", location=FAR), facility(local_id="node/1")])
    assert [f.id for f in resolved] == sorted(f.id for f in resolved)
