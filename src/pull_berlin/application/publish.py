"""Application service: the published catalog = machine snapshot + every human review.

Pure: takes facilities and reviews, returns views. Reading files is the CLI's job.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from pull_berlin.catalog.domain.assessment import AssessmentPolicy
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.publishing.views import FacilityView
from pull_berlin.review.domain import Review, latest


@dataclass(frozen=True)
class PublishResult:
    facilities: list[FacilityView]  # in scope: at least one offering
    reviewed: int  # facilities with at least one review applied
    unknown: list[Review]  # reviews of facilities that are not in the snapshot


@dataclass(frozen=True)
class Change:
    """How one facility looks on the map before and after some reviews."""

    facility_id: str
    name: str
    before: str
    after: str


def with_reviews(
    facilities: Sequence[Facility], reviews: Sequence[Review]
) -> tuple[list[Facility], list[Review]]:
    """Facilities with their reviews' statements added; plus the reviews that matched no facility."""
    by_facility: dict[str, list[Review]] = defaultdict(list)
    for review in latest(reviews):
        by_facility[review.facility_id].append(review)
    known = {f.id for f in facilities}
    unknown = [r for rs in by_facility.values() for r in rs if r.facility_id not in known]
    reviewed = [
        f.with_statements(tuple(s for r in by_facility.get(f.id, []) for s in r.statements()))
        for f in facilities
    ]
    return reviewed, unknown


def publish(
    facilities: Sequence[Facility], reviews: Sequence[Review], assessment: AssessmentPolicy | None = None
) -> PublishResult:
    assessment = assessment or AssessmentPolicy()
    reviewed, unknown = with_reviews(facilities, reviews)
    views = [FacilityView.of(f, assessment.assess(f.statements)) for f in reviewed]
    return PublishResult(
        facilities=[v for v in views if v.offerings],
        reviewed=sum(1 for v in views if v.reviewers),
        unknown=unknown,
    )


def changes(before: Sequence[FacilityView], after: Sequence[FacilityView]) -> list[Change]:
    """What a reader of the map would notice: a facility appears, disappears, or changes offerings."""
    old = {v.id: v for v in before}
    new = {v.id: v for v in after}
    result = []
    for facility_id in sorted(old.keys() | new.keys()):
        a, b = describe(old.get(facility_id)), describe(new.get(facility_id))
        if a != b:
            name = (new.get(facility_id) or old[facility_id]).name
            result.append(Change(facility_id, name, a, b))
    return result


def describe(view: FacilityView | None) -> str:
    """One line per facility as the map shows it, e.g. 'event_hire 0.97 (evening, night)'."""
    if view is None or not view.offerings:
        return "not on the map"
    windows = sorted({w for o in view.offerings for w in o.windows})
    offers = ", ".join(f"{o.kind} {o.confidence:.2f}" for o in view.offerings)
    return f"{offers} ({', '.join(windows)})" if windows else offers
