"""Hand-built domain inputs for unit tests. No I/O, no randomness."""

from __future__ import annotations

from pull_berlin.catalog.domain.claim import ClaimType, Evidence, Proposition, Stance, Statement
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.observation import Observation
from pull_berlin.catalog.domain.values import GeoPoint, SpaceCategory, SpaceName
from pull_berlin.shared_kernel import SourceKind

KREUZBERG = GeoPoint(lat=52.4988, lon=13.4401)


def evidence(
    *,
    source_id: str = "osm",
    kind: SourceKind = SourceKind.OPEN_GEODATA,
    strength: float = 1.0,
    stance: Stance = Stance.SUPPORTS,
    url: str = "https://example.org/doc",
    excerpt: str = "amenity=nightclub",
) -> Evidence:
    return Evidence(
        source_id=source_id, source_kind=kind, url=url, excerpt=excerpt, strength=strength, stance=stance
    )


def statement(
    claim_type: ClaimType, category: SpaceCategory | None = None, **evidence_args: object
) -> Statement:
    return Statement(Proposition(claim_type, category), evidence(**evidence_args))  # type: ignore[arg-type]


def observation(
    *,
    local_id: str = "node/1",
    name: str = "Beispielclub",
    location: GeoPoint = KREUZBERG,
    source_id: str = "osm",
    statements: tuple[Statement, ...] = (),
    website: str | None = None,
) -> Observation:
    return Observation(
        source_id=source_id,
        source_kind=SourceKind.OPEN_GEODATA,
        local_id=local_id,
        url=f"https://example.org/{local_id}",
        name=SpaceName(name),
        location=location,
        website=website,
        statements=statements,
    )


def facility(**observation_args: object) -> Facility:
    return Facility.from_observation(observation(**observation_args))  # type: ignore[arg-type]
