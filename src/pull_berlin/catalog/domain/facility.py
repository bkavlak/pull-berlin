"""Facility: the aggregate root of the catalog.

Ontology: a cco:Material Artifact (building, arch, boat, premises) that provides Event Spaces and
bears Space Use Roles. Sources describe facilities, so resolution and evidence live here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from pull_berlin.catalog.domain.assessment import Assessment, AssessmentPolicy
from pull_berlin.catalog.domain.claim import Statement
from pull_berlin.catalog.domain.observation import Observation
from pull_berlin.catalog.domain.values import GeoPoint, SpaceName
from pull_berlin.shared_kernel import CCO


@dataclass(frozen=True, order=True)
class ExternalRef:
    """Where a source knows this facility, e.g. osm:node/123."""

    source_id: str
    local_id: str

    def __str__(self) -> str:
        return f"{self.source_id}:{self.local_id}"


@dataclass(frozen=True)
class Facility:
    ONTOLOGY_TERM = CCO + "ont00000995"  # cco:Material Artifact

    id: str
    name: SpaceName
    location: GeoPoint
    refs: frozenset[ExternalRef]
    statements: tuple[Statement, ...]
    websites: frozenset[str]

    @classmethod
    def from_observation(cls, observation: Observation) -> Facility:
        ref = ExternalRef(observation.source_id, observation.local_id)
        return cls(
            id=str(ref),
            name=observation.name,
            location=observation.location.require_in_berlin(),
            refs=frozenset({ref}),
            statements=observation.statements,
            websites=frozenset({observation.website}) if observation.website else frozenset(),
        )

    def merge(self, other: Facility) -> Facility:
        """Same facility seen twice. Identity and location from the smaller id (deterministic);
        the longest name; everything else unioned — evidence is never dropped."""
        anchor = min(self, other, key=lambda f: f.id)
        name = max((self.name, other.name), key=lambda n: (len(n.display), n.display))
        return Facility(
            id=anchor.id,
            name=name,
            location=anchor.location,
            refs=self.refs | other.refs,
            statements=tuple(dict.fromkeys(self.statements + other.statements)),
            websites=self.websites | other.websites,
        )

    def absorb(self, observation: Observation) -> Facility:
        """Takes in what an enrichment source (crawled for this facility) says about it.
        Identity, name and location stay; the source reference and statements are added."""
        ref = ExternalRef(observation.source_id, observation.local_id)
        return replace(
            self,
            refs=self.refs | {ref},
            statements=tuple(dict.fromkeys(self.statements + observation.statements)),
        )

    def assess(self, policy: AssessmentPolicy) -> Assessment:
        return policy.assess(self.statements)
