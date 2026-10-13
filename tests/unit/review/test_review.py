from __future__ import annotations

import json
from datetime import date

import pytest

from pull_berlin.catalog.domain.assessment import AssessmentPolicy
from pull_berlin.catalog.domain.claim import ClaimType, Proposition, Stance
from pull_berlin.review.domain import Review, Shown, Verdict, latest, valid_reviewer
from pull_berlin.shared_kernel import SourceKind

from ..catalog.builders import statement

RENT = ClaimType.IS_RENTABLE_FOR_PRIVATE_EVENTS
HOSTS = ClaimType.HOSTS_EVENING_EVENTS
LATE = ClaimType.OPERATES_PAST_MIDNIGHT
DAY = date(2026, 10, 13)


def review(reviewer: str = "ada", facility_id: str = "osm:node/1", **verdicts: Verdict) -> Review:
    short = {"rentable": RENT, "hosts": HOSTS, "late": LATE}
    return Review(
        reviewer=reviewer,
        facility_id=facility_id,
        facility_name="Tresor",
        reviewed_on=DAY,
        verdicts={short[k]: v for k, v in (verdicts or {"rentable": Verdict.YES}).items()},
    )


def test_a_yes_supports_the_claim_as_human_review_evidence() -> None:
    (made,) = review(rentable=Verdict.YES).statements()
    assert made.proposition == Proposition(RENT)
    assert made.evidence.source_kind is SourceKind.HUMAN_REVIEW
    assert made.evidence.stance is Stance.SUPPORTS
    assert made.evidence.source_id == "review:ada"


def test_a_no_opposes_the_claim() -> None:
    (made,) = review(hosts=Verdict.NO).statements()
    assert made.evidence.stance is Stance.OPPOSES


def test_unsure_says_nothing() -> None:
    made = review(rentable=Verdict.YES, late=Verdict.UNSURE).statements()
    assert [s.proposition.claim_type for s in made] == [RENT]


def test_a_review_of_only_unsure_answers_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one yes or no"):
        review(rentable=Verdict.UNSURE)


def test_categories_cannot_be_reviewed_yet() -> None:
    with pytest.raises(ValueError, match="cannot review"):
        Review("ada", "osm:node/1", "Tresor", DAY, {ClaimType.OPERATES_IN_EVENING: Verdict.YES})


@pytest.mark.parametrize("handle", ["", "-ada", "ada lovelace", "../etc/passwd", "a" * 40])
def test_reviewer_must_be_a_github_user_name(handle: str) -> None:
    with pytest.raises(ValueError, match="GitHub user name"):
        valid_reviewer(handle)


def test_a_human_no_takes_a_well_sourced_offering_off_the_map() -> None:
    policy = AssessmentPolicy()
    site = statement(RENT, source_id="site", kind=SourceKind.VENUE_OWN_SITE, strength=0.9)
    before = policy.assess([site])
    after = policy.assess([site, *review(rentable=Verdict.NO).statements()])
    assert before.offerings and before.confidence(Proposition(RENT)) > 0.8
    assert not after.offerings
    assert after.confidence(Proposition(RENT)) < 0.05


def test_a_human_yes_puts_an_unclaimed_offering_on_the_map() -> None:
    assessed = AssessmentPolicy().assess(review(rentable=Verdict.YES).statements())
    assert [o.kind.value for o in assessed.offerings] == ["event_rental"]


def test_record_round_trips_through_json() -> None:
    original = Review(
        "ada",
        "osm:node/1",
        "Tresor",
        DAY,
        {RENT: Verdict.NO, LATE: Verdict.YES},
        model="laya-0.4.6-multilingual",
        shown={RENT: Shown("https://tresor.example/", "Mieten Sie unseren Saal", 0.93)},
        note="Only their own club nights",
    )
    assert Review.from_json(original.to_json()) == original


def test_record_uses_short_claim_names() -> None:
    record = json.loads(review(rentable=Verdict.NO).to_json())
    assert record["verdicts"] == {"rentable": "no"}
    assert record["facility"] == "osm:node/1"


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ('{"facility": "osm:node/1"}', "missing"),
        (
            '{"facility": "x", "reviewer": "ada", "reviewed_on": "2026-10-13", "verdicts": {"vibe": "yes"}}',
            "unknown claim",
        ),
        (
            '{"facility": "x", "reviewer": "ada", "reviewed_on": "2026-10-13", '
            '"verdicts": {"late": "maybe"}}',
            "maybe",
        ),
    ],
)
def test_malformed_records_are_rejected(line: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Review.from_json(line)


def test_only_a_reviewers_last_word_on_a_facility_counts() -> None:
    first = review(rentable=Verdict.YES)
    changed_mind = review(rentable=Verdict.NO)
    other_person = review(reviewer="grace", rentable=Verdict.YES)
    other_place = review(facility_id="osm:node/2")
    assert latest([first, other_person, changed_mind, other_place]) == [
        other_person,
        changed_mind,
        other_place,
    ]
