"""Application service: fetch every source, translate, resolve, assess, return views and a report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from pull_berlin.catalog.domain.assessment import AssessmentPolicy
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.resolution import ResolutionPolicy
from pull_berlin.catalog.domain.values import NotInBerlinError
from pull_berlin.publishing.views import FacilityView
from pull_berlin.sourcing.ports import Fetcher, SourceAdapter


@dataclass(frozen=True)
class PullReport:
    observations: int
    outside_berlin: int
    facilities: int
    in_scope: int
    observations_per_source: dict[str, int] = field(default_factory=dict)


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
) -> PullResult:
    """`include_all=False` keeps only facilities with an evening/night offering (the catalog's scope)."""
    assessment = assessment or AssessmentPolicy()
    resolution = resolution or ResolutionPolicy()

    candidates: list[Facility] = []
    per_source: Counter[str] = Counter()
    outside_berlin = 0
    for source in sources:
        for request in source.requests():
            for observation in source.parse(fetcher.fetch(request)):
                per_source[observation.source_id] += 1
                try:
                    candidates.append(Facility.from_observation(observation))
                except NotInBerlinError:
                    outside_berlin += 1

    facilities = resolution.resolve(candidates)
    views = [FacilityView.of(f, assessment.assess(f.statements)) for f in facilities]
    in_scope = [view for view in views if view.offerings]
    return PullResult(
        facilities=views if include_all else in_scope,
        report=PullReport(
            observations=sum(per_source.values()),
            outside_berlin=outside_berlin,
            facilities=len(facilities),
            in_scope=len(in_scope),
            observations_per_source=dict(per_source),
        ),
    )
