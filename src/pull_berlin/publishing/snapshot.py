"""Reads a catalog snapshot (the JSON export) back into facilities.

The JSON export keeps every claim with all its evidence, so it is a complete record of what the
sources said. `data/catalog/facilities.json` is such a snapshot, committed to git: publishing
the map and reviewing it need neither the network nor the raw cache.
"""

from __future__ import annotations

import json

from pull_berlin.catalog.domain.claim import Evidence, Proposition, Stance, Statement
from pull_berlin.catalog.domain.facility import ExternalRef, Facility
from pull_berlin.catalog.domain.values import GeoPoint, SpaceName
from pull_berlin.shared_kernel import SourceKind


def read_snapshot(text: str) -> list[Facility]:
    return [_facility(record) for record in json.loads(text)["facilities"]]


def _facility(record: dict[str, object]) -> Facility:
    claims = record["claims"]
    assert isinstance(claims, list)
    statements = tuple(
        Statement(
            Proposition.from_label(claim["proposition"]),
            Evidence(
                source_id=e["source"],
                source_kind=SourceKind(e["kind"]),
                url=e["url"],
                excerpt=e["excerpt"],
                strength=float(e["strength"]),
                stance=Stance(e["stance"]),
            ),
        )
        for claim in claims
        for e in claim["evidence"]
    )
    refs = record["refs"]
    websites = record["websites"]
    assert isinstance(refs, list) and isinstance(websites, list)
    return Facility(
        id=str(record["id"]),
        name=SpaceName(str(record["name"])),
        location=GeoPoint(float(str(record["lat"])), float(str(record["lon"]))),
        refs=frozenset(ExternalRef(*ref.split(":", 1)) for ref in refs),
        statements=statements,
        websites=frozenset(websites),
    )
