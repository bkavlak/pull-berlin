"""What one source document says about one candidate facility. Produced by source adapters (ACL)."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pull_berlin.catalog.domain.claim import Statement
from pull_berlin.catalog.domain.values import GeoPoint, SpaceName
from pull_berlin.shared_kernel import PB, SourceKind


@dataclass(frozen=True)
class Passage:
    """Free text from a source document that still has to be read (by a classifier) to yield statements."""

    text: str
    url: str


@dataclass(frozen=True)
class Observation:
    ONTOLOGY_TERM = PB + "Observation"

    source_id: str
    source_kind: SourceKind
    local_id: str
    url: str
    name: SpaceName
    location: GeoPoint
    website: str | None = None
    statements: tuple[Statement, ...] = ()
    passages: tuple[Passage, ...] = ()

    def with_statements(self, statements: tuple[Statement, ...]) -> Observation:
        return replace(self, statements=self.statements + statements)
