"""Application service.

Phase 1 (discovery): fetch every source, translate, resolve into facilities.
Phase 2 (enrichment): visit each facility's own sources (e.g. website), read their passages with
the classifier, absorb the resulting statements. Then assess and return views plus a report.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from pull_berlin.catalog.domain.assessment import AssessmentPolicy
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.observation import Observation
from pull_berlin.catalog.domain.resolution import ResolutionPolicy
from pull_berlin.catalog.domain.values import NotInBerlinError
from pull_berlin.extraction.policy import ExtractionPolicy
from pull_berlin.extraction.ports import TextClassifier
from pull_berlin.publishing.views import FacilityView
from pull_berlin.sourcing.ports import Enricher, Fetcher, SourceAdapter


@dataclass(frozen=True)
class PullReport:
    observations: int
    outside_berlin: int
    facilities: int
    in_scope: int
    observations_per_source: dict[str, int] = field(default_factory=dict)
    sites_attempted: int = 0
    sites_observed: int = 0
    passages_classified: int = 0


@dataclass(frozen=True)
class PullResult:
    facilities: list[FacilityView]
    report: PullReport


def pull(
    sources: Sequence[SourceAdapter],
    fetcher: Fetcher,
    assessment: AssessmentPolicy | None = None,
    resolution: ResolutionPolicy | None = None,
    include_all: bool = False,
    enrichers: Sequence[Enricher] = (),
    classifier: TextClassifier | None = None,
    extraction: ExtractionPolicy | None = None,
    enrich_limit: int | None = None,
) -> PullResult:
    """`include_all=False` keeps only facilities with an evening/night offering (the catalog's scope).
    `enrich_limit` caps how many facilities (with a website, by id) are enriched — for samples."""
    assessment = assessment or AssessmentPolicy()
    resolution = resolution or ResolutionPolicy()
    reader = _Reader(classifier, extraction or ExtractionPolicy())

    candidates: list[Facility] = []
    per_source: Counter[str] = Counter()
    outside_berlin = 0
    for source in sources:
        for request in source.requests():
            for observation in source.parse(fetcher.fetch(request)):
                per_source[observation.source_id] += 1
                try:
                    candidates.append(Facility.from_observation(reader.read(observation)))
                except NotInBerlinError:
                    outside_berlin += 1
    facilities = resolution.resolve(candidates)

    attempted = observed = 0
    if enrichers:
        with_site = [f for f in facilities if f.websites]
        chosen = (
            {f.id for f in with_site[:enrich_limit]}
            if enrich_limit is not None
            else {f.id for f in with_site}
        )
        enriched = []
        for facility in facilities:
            if facility.id in chosen:
                for enricher in enrichers:
                    attempted += 1
                    found = enricher.observe(facility, fetcher)
                    if found is not None:
                        observed += 1
                        per_source[found.source_id] += 1
                        facility = facility.absorb(reader.read(found))
            enriched.append(facility)
        facilities = enriched

    views = [FacilityView.of(f, assessment.assess(f.statements)) for f in facilities]
    in_scope = [view for view in views if view.offerings]
    return PullResult(
        facilities=views if include_all else in_scope,
        report=PullReport(
            observations=sum(per_source.values()) - observed,
            outside_berlin=outside_berlin,
            facilities=len(facilities),
            in_scope=len(in_scope),
            observations_per_source=dict(per_source),
            sites_attempted=attempted,
            sites_observed=observed,
            passages_classified=reader.passages_classified,
        ),
    )


class _Reader:
    """Turns an observation's passages into statements, if there is a classifier."""

    def __init__(self, classifier: TextClassifier | None, policy: ExtractionPolicy) -> None:
        self._classifier = classifier
        self._policy = policy
        self.passages_classified = 0

    def read(self, observation: Observation) -> Observation:
        if self._classifier is None or not observation.passages:
            return observation
        judgements = self._classifier.classify([p.text for p in observation.passages])
        self.passages_classified += len(observation.passages)
        statements = self._policy.statements(
            observation.passages, judgements, observation.source_id, observation.source_kind
        )
        return observation.with_statements(statements)
