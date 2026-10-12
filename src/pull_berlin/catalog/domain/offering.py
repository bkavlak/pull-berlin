"""Ways a facility can be used. Ontology: roles (pb:SpaceUseRole) inhering in the facility."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pull_berlin.catalog.domain.values import TimeWindow
from pull_berlin.shared_kernel import PB


class OfferingKind(Enum):
    """Extension point: new use cases (coworking, rehearsal, …) are new members + ontology roles."""

    EVENT_HIRE = "event_hire"  # you can book the space for your own event
    EVENT_HOSTING = "event_hosting"  # the operator runs its own evening/night program

    @property
    def ontology_term(self) -> str:
        return PB + {"event_hire": "EventHireRole", "event_hosting": "EventHostingRole"}[self.value]


@dataclass(frozen=True)
class Offering:
    """Derived by AssessmentPolicy from claims; never set by hand. Empty windows mean 'unknown'."""

    ONTOLOGY_TERM = PB + "SpaceUseRole"

    kind: OfferingKind
    windows: frozenset[TimeWindow]
    confidence: float
