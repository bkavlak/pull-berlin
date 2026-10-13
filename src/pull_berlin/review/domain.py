"""A Review: one person's yes/no on the catalog's claims about one facility.

A review is evidence like any other (SourceKind.HUMAN_REVIEW, high prior). It joins the noisy-OR
instead of overwriting the machine evidence: a "no" drives a claim towards zero, a "yes" lifts it
above the threshold. Disagreement between people stays visible as lower confidence.

Records are JSON lines in `data/reviews/<reviewer>.jsonl` — one file per reviewer, so pull
requests from different people never touch the same file.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from pull_berlin.catalog.domain.claim import ClaimType, Evidence, Proposition, Stance, Statement
from pull_berlin.shared_kernel import SourceKind

REVIEWS_DIR = "data/reviews"

# The claims a person is asked about, by their short name on the command line and in records.
REVIEWED_CLAIMS: Mapping[str, ClaimType] = {
    "rentable": ClaimType.IS_RENTABLE_FOR_PRIVATE_EVENTS,
    "hosts": ClaimType.HOSTS_EVENING_EVENTS,
    "late": ClaimType.OPERATES_PAST_MIDNIGHT,
}

# How the question is put to a person (plain words; the classifier gets QUESTION_SET_V1).
QUESTIONS: Mapping[ClaimType, str] = {
    ClaimType.IS_RENTABLE_FOR_PRIVATE_EVENTS: "Can you rent this place, or a room in it, "
    "for your own private event (party, wedding, company event)?",
    ClaimType.HOSTS_EVENING_EVENTS: "Does it run its own public evening events "
    "(concerts, club nights, parties, readings, screenings)?",
    ClaimType.OPERATES_PAST_MIDNIGHT: "Is it open, or do its events go on, past midnight?",
}

_HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")  # a GitHub user name
_SHORT_NAME = {claim_type: short for short, claim_type in REVIEWED_CLAIMS.items()}


class Verdict(Enum):
    YES = "yes"
    NO = "no"
    UNSURE = "unsure"


def valid_reviewer(handle: str) -> str:
    if not _HANDLE.match(handle):
        raise ValueError(f"reviewer must be a GitHub user name (letters, digits, '-'), got {handle!r}")
    return handle


@dataclass(frozen=True)
class Shown:
    """What the reviewer was shown for one claim: the passage the model rated highest, and its rating."""

    url: str
    text: str
    probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"probability must be within 0..1, got {self.probability}")


@dataclass(frozen=True)
class Review:
    reviewer: str
    facility_id: str
    facility_name: str
    reviewed_on: date
    verdicts: Mapping[ClaimType, Verdict]
    model: str | None = None
    shown: Mapping[ClaimType, Shown] = field(default_factory=dict)
    note: str = ""

    def __post_init__(self) -> None:
        valid_reviewer(self.reviewer)
        if not self.facility_id:
            raise ValueError("a review needs the id of the facility it is about")
        unknown = set(self.verdicts) - set(REVIEWED_CLAIMS.values())
        if unknown:
            raise ValueError(f"cannot review {sorted(c.value for c in unknown)}")
        if all(v is Verdict.UNSURE for v in self.verdicts.values()):
            raise ValueError("a review needs at least one yes or no")

    def statements(self) -> tuple[Statement, ...]:
        """The review as catalog evidence: yes supports, no opposes, unsure says nothing."""
        result = []
        for claim_type, verdict in self.verdicts.items():
            if verdict is Verdict.UNSURE:
                continue
            excerpt = f"{self.reviewer} checked on {self.reviewed_on.isoformat()}: {verdict.value}"
            evidence = Evidence(
                source_id=f"review:{self.reviewer}",
                source_kind=SourceKind.HUMAN_REVIEW,
                url=f"{REVIEWS_DIR}/{self.reviewer}.jsonl",
                excerpt=f"{excerpt} — {self.note}" if self.note else excerpt,
                strength=1.0,
                stance=Stance.SUPPORTS if verdict is Verdict.YES else Stance.OPPOSES,
            )
            result.append(Statement(Proposition(claim_type), evidence))
        return tuple(result)

    def to_json(self) -> str:
        record: dict[str, Any] = {
            "facility": self.facility_id,
            "name": self.facility_name,
            "reviewer": self.reviewer,
            "reviewed_on": self.reviewed_on.isoformat(),
            "verdicts": {_SHORT_NAME[c]: v.value for c, v in self.verdicts.items()},
        }
        if self.note:
            record["note"] = self.note
        if self.model:
            record["model"] = self.model
        if self.shown:
            record["shown"] = {
                _SHORT_NAME[c]: {"url": s.url, "probability": round(s.probability, 4), "text": s.text}
                for c, s in self.shown.items()
            }
        return json.dumps(record, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> Review:
        record = json.loads(line)
        try:
            return cls(
                reviewer=record["reviewer"],
                facility_id=record["facility"],
                facility_name=record.get("name", ""),
                reviewed_on=date.fromisoformat(record["reviewed_on"]),
                verdicts={_claim(k): Verdict(v) for k, v in record["verdicts"].items()},
                model=record.get("model"),
                shown={
                    _claim(k): Shown(s["url"], s["text"], float(s["probability"]))
                    for k, s in record.get("shown", {}).items()
                },
                note=record.get("note", ""),
            )
        except KeyError as missing:
            raise ValueError(f"review record is missing {missing}") from None


def latest(reviews: Iterable[Review]) -> list[Review]:
    """A person may change their mind: per reviewer and facility only the last review counts."""
    last: dict[tuple[str, str], Review] = {}
    for review in reviews:
        last.pop((review.reviewer, review.facility_id), None)
        last[(review.reviewer, review.facility_id)] = review
    return list(last.values())


def _claim(short: str) -> ClaimType:
    if short not in REVIEWED_CLAIMS:
        raise ValueError(f"unknown claim {short!r}; expected one of {sorted(REVIEWED_CLAIMS)}")
    return REVIEWED_CLAIMS[short]
