"""Application service for human review: what to check next, and what the model says about it.

A ReviewItem shows a person, for one facility, what the catalog believes now and what the model
(Laya, or the keyword baseline) reads on the facility's own website, with the passage it rated
highest. The person answers yes / no / unsure per claim; `ReviewItem.review` turns that into a
Review record.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from pull_berlin.catalog.domain.assessment import AssessmentPolicy
from pull_berlin.catalog.domain.claim import ClaimType, Evidence, Proposition, Stance
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.values import SpaceName
from pull_berlin.extraction.ports import TextClassifier
from pull_berlin.review.domain import QUESTIONS, REVIEWED_CLAIMS, Review, Shown, Verdict, latest
from pull_berlin.sourcing.ports import Enricher, Fetcher

_ASKED_FIRST = (ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS, ClaimType.HOSTS_EVENING_EVENTS)


@dataclass(frozen=True)
class ClaimCheck:
    claim_type: ClaimType
    question: str
    catalog_confidence: float
    sources: tuple[str, ...]  # what each source says now, e.g. "osm: yes", "review:ada: no"
    shown: Shown | None  # the model's best passage; None if the model found nothing or did not run


@dataclass(frozen=True)
class ReviewItem:
    facility_id: str
    name: str
    category: str | None
    websites: tuple[str, ...]
    links: tuple[str, ...]  # pages a person can open to check (OpenStreetMap, the website)
    checks: tuple[ClaimCheck, ...]
    model: str | None
    pages_read: int

    def review(
        self, reviewer: str, answers: Mapping[str, Verdict], reviewed_on: date, note: str = ""
    ) -> Review:
        verdicts = {REVIEWED_CLAIMS[short]: verdict for short, verdict in answers.items()}
        return Review(
            reviewer=reviewer,
            facility_id=self.facility_id,
            facility_name=self.name,
            reviewed_on=reviewed_on,
            verdicts=verdicts,
            model=self.model,
            shown={
                c.claim_type: c.shown
                for c in self.checks
                if c.shown and verdicts.get(c.claim_type, Verdict.UNSURE) is not Verdict.UNSURE
            },
            note=note,
        )

    def to_dict(self) -> dict[str, Any]:
        short = {claim_type: name for name, claim_type in REVIEWED_CLAIMS.items()}
        return {
            "facility": self.facility_id,
            "name": self.name,
            "category": self.category,
            "websites": list(self.websites),
            "links": list(self.links),
            "model": self.model,
            "pages_read": self.pages_read,
            "checks": [
                {
                    "claim": short[c.claim_type],
                    "question": c.question,
                    "catalog_confidence": c.catalog_confidence,
                    "sources": list(c.sources),
                    "model_probability": c.shown.probability if c.shown else None,
                    "passage_url": c.shown.url if c.shown else None,
                    "passage": c.shown.text if c.shown else None,
                }
                for c in self.checks
            ],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ReviewItem:
        return cls(
            facility_id=raw["facility"],
            name=raw["name"],
            category=raw.get("category"),
            websites=tuple(raw.get("websites", ())),
            links=tuple(raw.get("links", ())),
            model=raw.get("model"),
            pages_read=int(raw.get("pages_read", 0)),
            checks=tuple(
                ClaimCheck(
                    claim_type=REVIEWED_CLAIMS[c["claim"]],
                    question=c["question"],
                    catalog_confidence=float(c["catalog_confidence"]),
                    sources=tuple(c["sources"]),
                    shown=Shown(c["passage_url"], c["passage"], float(c["model_probability"]))
                    if c.get("passage") is not None
                    else None,
                )
                for c in raw["checks"]
            ),
        )


def choose_next(
    facilities: Sequence[Facility],
    reviews: Sequence[Review],
    skipped: Collection[str] = (),
    assessment: AssessmentPolicy | None = None,
) -> Facility | None:
    """The unreviewed facility (with a website) the catalog is least sure about.

    Uncertainty = how close hire or hosting confidence is to the threshold: a review there is most
    likely to change what the map shows. Ties go by id, so the queue is reproducible.
    """
    assessment = assessment or AssessmentPolicy()
    done = {r.facility_id for r in latest(reviews)} | set(skipped)
    candidates = [f for f in facilities if f.websites and f.id not in done]

    def uncertainty(facility: Facility) -> float:
        judged = assessment.assess(facility.statements)
        return min(abs(judged.confidence(Proposition(c)) - assessment.threshold) for c in _ASKED_FIRST)

    return min(candidates, key=lambda f: (round(uncertainty(f), 3), f.id), default=None)


def find(facilities: Sequence[Facility], query: str) -> list[Facility]:
    """Facilities whose id is `query`, or whose name contains it (accents and case ignored)."""
    exact = [f for f in facilities if f.id == query]
    if exact:
        return exact
    wanted = SpaceName(query).normalized
    return [f for f in facilities if wanted in f.name.normalized]


def prepare(
    facility: Facility,
    enricher: Enricher | None,
    fetcher: Fetcher | None,
    classifier: TextClassifier | None,
    assessment: AssessmentPolicy | None = None,
) -> ReviewItem:
    """Reads the facility's website now and asks the classifier about every passage.

    Without an enricher, fetcher or classifier (or when the site cannot be read) the item still
    shows the catalog's belief, so a person can review from their own knowledge.
    """
    assessment = assessment or AssessmentPolicy()
    judged = assessment.assess(facility.statements)
    observation = (
        enricher.observe(facility, fetcher)
        if enricher and fetcher and classifier and facility.websites
        else None
    )
    passages = list(observation.passages) if observation else []
    judgements = classifier.classify([p.text for p in passages]) if classifier and passages else []

    checks = []
    for claim_type in REVIEWED_CLAIMS.values():
        proposition = Proposition(claim_type)
        rated = [(j.get(proposition, 0.0), p) for j, p in zip(judgements, passages, strict=True)]
        best = max(rated, key=lambda item: item[0], default=None)
        claim = next((c for c in judged.claims if c.proposition == proposition), None)
        checks.append(
            ClaimCheck(
                claim_type=claim_type,
                question=QUESTIONS[claim_type],
                catalog_confidence=round(judged.confidence(proposition), 3),
                sources=_sources(claim.evidence) if claim else (),
                shown=Shown(best[1].url, best[1].text, round(best[0], 4)) if best and best[0] > 0 else None,
            )
        )
    osm = [
        f"https://www.openstreetmap.org/{r.local_id}" for r in sorted(facility.refs) if r.source_id == "osm"
    ]
    return ReviewItem(
        facility_id=facility.id,
        name=facility.name.display,
        category=judged.primary_category.value if judged.primary_category else None,
        websites=tuple(sorted(facility.websites)),
        links=(*osm, *sorted(facility.websites)),
        checks=tuple(checks),
        model=classifier.model_id if classifier and passages else None,
        pages_read=len({p.url for p in passages}),
    )


def _sources(evidence: Sequence[Evidence]) -> tuple[str, ...]:
    said = {(e.source_id, "yes" if e.stance is Stance.SUPPORTS else "no") for e in evidence}
    return tuple(f"{source}: {answer}" for source, answer in sorted(said))
