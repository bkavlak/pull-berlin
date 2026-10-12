"""Read model: flat, serializable views of assessed facilities. No behaviour beyond derivation."""

from __future__ import annotations

from dataclasses import dataclass

from pull_berlin.catalog.domain.assessment import Assessment
from pull_berlin.catalog.domain.facility import Facility


@dataclass(frozen=True)
class EvidenceView:
    source: str
    url: str
    excerpt: str
    stance: str
    strength: float


@dataclass(frozen=True)
class ClaimView:
    proposition: str
    confidence: float
    evidence: tuple[EvidenceView, ...]


@dataclass(frozen=True)
class OfferingView:
    kind: str
    windows: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class FacilityView:
    id: str
    name: str
    lat: float
    lon: float
    category: str | None
    category_degree: float
    offerings: tuple[OfferingView, ...] = ()
    refs: tuple[str, ...] = ()
    websites: tuple[str, ...] = ()
    claims: tuple[ClaimView, ...] = ()

    @property
    def evening(self) -> bool:
        return any("evening" in o.windows for o in self.offerings)

    @property
    def night(self) -> bool:
        return any("night" in o.windows for o in self.offerings)

    @property
    def max_confidence(self) -> float:
        return max((o.confidence for o in self.offerings), default=0.0)

    @classmethod
    def of(cls, facility: Facility, assessment: Assessment) -> FacilityView:
        category = assessment.categories[0] if assessment.categories else None
        return cls(
            id=facility.id,
            name=facility.name.display,
            lat=facility.location.lat,
            lon=facility.location.lon,
            category=category[0].value if category else None,
            category_degree=_round(category[1]) if category else 0.0,
            offerings=tuple(
                OfferingView(o.kind.value, tuple(sorted(w.value for w in o.windows)), _round(o.confidence))
                for o in assessment.offerings
            ),
            refs=tuple(sorted(str(ref) for ref in facility.refs)),
            websites=tuple(sorted(facility.websites)),
            claims=tuple(
                ClaimView(
                    proposition=claim.proposition.label,
                    confidence=_round(claim.confidence),
                    evidence=tuple(
                        EvidenceView(e.source_id, e.url, e.excerpt, e.stance.value, e.strength)
                        for e in claim.evidence
                    ),
                )
                for claim in assessment.claims
            ),
        )


def _round(value: float) -> float:
    return round(value, 3)
