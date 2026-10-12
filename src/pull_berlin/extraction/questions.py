"""The questions we ask about free text. Owned by the domain, not by any model.

Instructions are English; the multilingual model reads German and English text against them.
Category criteria are the prototype descriptions of pb:SpaceCategory (radial categories).
Bump `version` whenever wording changes: cached answers are keyed by it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pull_berlin.catalog.domain.claim import ClaimType, Proposition
from pull_berlin.catalog.domain.values import SpaceCategory


@dataclass(frozen=True)
class YesNoQuestion:
    proposition: Proposition
    instructions: str

    @property
    def key(self) -> str:
        return self.proposition.claim_type.value


@dataclass(frozen=True)
class CategoryQuestion:
    instructions: str
    criteria: Mapping[SpaceCategory, str]

    key = "space_category"


@dataclass(frozen=True)
class QuestionSet:
    version: str
    yes_no: tuple[YesNoQuestion, ...]
    category: CategoryQuestion


QUESTION_SET_V1 = QuestionSet(
    version="v1",
    yes_no=(
        YesNoQuestion(
            Proposition(ClaimType.IS_HIREABLE_FOR_PRIVATE_EVENTS),
            "Does the text say that customers can rent or book this place, or a room in it, "
            "for their own private event, party, wedding or company event?",
        ),
        YesNoQuestion(
            Proposition(ClaimType.HOSTS_EVENING_EVENTS),
            "Does the text say that this place organizes its own evening events open to the public, "
            "such as concerts, club nights, parties, theatre, readings or screenings?",
        ),
        YesNoQuestion(
            Proposition(ClaimType.OPERATES_PAST_MIDNIGHT),
            "Does the text say that this place is open, or that its events continue, after midnight?",
        ),
    ),
    category=CategoryQuestion(
        "Which kind of place does the text describe?",
        {
            SpaceCategory.CLUB: "a club with sound system and dance floor, "
            "mainly open at night with DJs or live music",
            SpaceCategory.BAR: "a bar or pub centred on a counter serving drinks, open in the evening",
            SpaceCategory.EVENT_HALL: "an event hall rented out for conferences, parties and weddings, "
            "without its own daily programme",
            SpaceCategory.LOFT: "a converted industrial or upper-floor open-plan room "
            "rented for private events and shoots",
            SpaceCategory.GALLERY: "an exhibition room or gallery "
            "that also hosts openings and evening events",
            SpaceCategory.RESTAURANT: "a restaurant serving meals at tables, possibly with a bookable room",
            SpaceCategory.CULTURAL_CENTRE: "a cultural or community centre with concerts, theatre, readings "
            "and community events",
            SpaceCategory.OTHER: "something else, far from all of the descriptions above",
        },
    ),
)
