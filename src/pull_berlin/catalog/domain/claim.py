"""What sources say about a facility (Statements) and what the catalog believes (Claims).

Ontology: Evidence and Claim are cco:Descriptive Information Content Entities. Degrees of belief
live here, never on world entities (Smith & Mark: vagueness is in our concepts, not in the world).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pull_berlin.catalog.domain.values import SpaceCategory
from pull_berlin.shared_kernel import PB, SourceKind


class ClaimType(Enum):
    IS_HIREABLE_FOR_PRIVATE_EVENTS = "is_hireable_for_private_events"
    HOSTS_EVENING_EVENTS = "hosts_evening_events"
    OPERATES_IN_EVENING = "operates_in_evening"
    OPERATES_PAST_MIDNIGHT = "operates_past_midnight"
    FALLS_UNDER_CATEGORY = "falls_under_category"


class Stance(Enum):
    SUPPORTS = "supports"
    OPPOSES = "opposes"


@dataclass(frozen=True)
class Proposition:
    """The content of a claim, e.g. 'is hireable' or 'falls under category club'."""

    claim_type: ClaimType
    category: SpaceCategory | None = None

    def __post_init__(self) -> None:
        needs_category = self.claim_type is ClaimType.FALLS_UNDER_CATEGORY
        if needs_category and self.category is None:
            raise ValueError("a category proposition needs a category")
        if not needs_category and self.category is not None:
            raise ValueError(f"{self.claim_type.value} does not take a category")

    @property
    def label(self) -> str:
        return self.category.value if self.category else self.claim_type.value


@dataclass(frozen=True)
class Evidence:
    """One excerpt from one source document that supports or opposes a proposition."""

    ONTOLOGY_TERM = PB + "Evidence"

    source_id: str
    source_kind: SourceKind
    url: str
    excerpt: str
    strength: float = 1.0
    stance: Stance = Stance.SUPPORTS

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be within 0..1, got {self.strength}")
        if not self.url:
            raise ValueError("evidence needs the URL of the document it came from")


@dataclass(frozen=True)
class Statement:
    """A source saying something: a proposition plus the evidence for it."""

    proposition: Proposition
    evidence: Evidence


@dataclass(frozen=True)
class Claim:
    """The catalog's belief in a proposition, computed from all evidence. Never without evidence."""

    ONTOLOGY_TERM = PB + "Claim"

    proposition: Proposition
    evidence: tuple[Evidence, ...]
    confidence: float

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("a claim without evidence cannot exist")
