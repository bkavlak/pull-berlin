"""Turns statements into claims with confidence, offerings and graded categories.

One deep module on purpose: confidence and offering derivation change together and share all
their inputs, so callers get one call (`assess`) instead of three policies to wire up.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from pull_berlin.catalog.domain.claim import Claim, ClaimType, Evidence, Proposition, Stance, Statement
from pull_berlin.catalog.domain.offering import Offering, OfferingKind
from pull_berlin.catalog.domain.values import SpaceCategory, TimeWindow
from pull_berlin.shared_kernel import SourceKind

DEFAULT_PRIORS: Mapping[SourceKind, float] = {
    SourceKind.OPEN_GEODATA: 0.8,
    SourceKind.MAPS_AND_REVIEWS: 0.6,
    SourceKind.RENTAL_MARKETPLACE: 0.9,
    SourceKind.EVENT_LISTING: 0.85,
    SourceKind.VENUE_OWN_SITE: 0.95,
    SourceKind.OFFICIAL_COMMUNITY: 0.9,
    SourceKind.SOCIAL: 0.5,
    SourceKind.HUMAN_REVIEW: 0.98,
}

_OFFERING_CLAIMS = {
    OfferingKind.EVENT_HIRE: ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS,
    OfferingKind.EVENT_HOSTING: ClaimType.HOSTS_EVENING_EVENTS,
}


@dataclass(frozen=True)
class Assessment:
    claims: tuple[Claim, ...]
    offerings: tuple[Offering, ...]
    categories: tuple[tuple[SpaceCategory, float], ...]

    def confidence(self, proposition: Proposition) -> float:
        return next((c.confidence for c in self.claims if c.proposition == proposition), 0.0)

    @property
    def primary_category(self) -> SpaceCategory | None:
        return self.categories[0][0] if self.categories else None


class AssessmentPolicy:
    """Confidence per proposition = support x (1 - opposition), each a noisy-OR over sources.

    A source contributes prior(kind) x strongest evidence strength it gave, once per stance, so a
    source repeating itself (OSM node + building way) cannot inflate belief.
    """

    def __init__(
        self,
        priors: Mapping[SourceKind, float] = DEFAULT_PRIORS,
        threshold: float = 0.6,
        default_prior: float = 0.5,
    ) -> None:
        for value in (threshold, default_prior, *priors.values()):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"probabilities must be within 0..1, got {value}")
        self._priors = dict(priors)
        self.threshold = threshold
        self.default_prior = default_prior

    def assess(self, statements: Iterable[Statement]) -> Assessment:
        evidence_by_proposition: dict[Proposition, list[Evidence]] = defaultdict(list)
        for statement in statements:
            evidence_by_proposition[statement.proposition].append(statement.evidence)

        claims = tuple(
            Claim(proposition, tuple(evidence), self._confidence(evidence))
            for proposition, evidence in evidence_by_proposition.items()
        )
        believed = {claim.proposition: claim.confidence for claim in claims}
        return Assessment(
            claims=claims,
            offerings=self._offerings(believed),
            categories=self._categories(believed),
        )

    def _confidence(self, evidence: list[Evidence]) -> float:
        return self._noisy_or(evidence, Stance.SUPPORTS) * (1.0 - self._noisy_or(evidence, Stance.OPPOSES))

    def _noisy_or(self, evidence: list[Evidence], stance: Stance) -> float:
        strongest_per_source: dict[str, float] = {}
        for item in evidence:
            if item.stance is stance:
                weight = self._priors.get(item.source_kind, self.default_prior) * item.strength
                strongest_per_source[item.source_id] = max(
                    weight, strongest_per_source.get(item.source_id, 0.0)
                )
        disbelief = 1.0
        for weight in strongest_per_source.values():
            disbelief *= 1.0 - weight
        return 1.0 - disbelief

    def _offerings(self, believed: Mapping[Proposition, float]) -> tuple[Offering, ...]:
        def conf(claim_type: ClaimType) -> float:
            return believed.get(Proposition(claim_type), 0.0)

        windows = set()
        if max(conf(ClaimType.OPERATES_IN_EVENING), conf(ClaimType.HOSTS_EVENING_EVENTS)) >= self.threshold:
            windows.add(TimeWindow.EVENING)
        if conf(ClaimType.OPERATES_PAST_MIDNIGHT) >= self.threshold:
            windows.add(TimeWindow.NIGHT)

        return tuple(
            Offering(kind, frozenset(windows), conf(claim_type))
            for kind, claim_type in _OFFERING_CLAIMS.items()
            if conf(claim_type) >= self.threshold
        )

    @staticmethod
    def _categories(believed: Mapping[Proposition, float]) -> tuple[tuple[SpaceCategory, float], ...]:
        graded = [
            (p.category, degree) for p, degree in believed.items() if p.category is not None and degree > 0
        ]
        return tuple(sorted(graded, key=lambda item: (-item[1], item[0].value)))
