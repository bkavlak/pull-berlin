"""Shared kernel: vocabulary every bounded context agrees on (DDD context map: Shared Kernel)."""

from __future__ import annotations

from enum import Enum

PB = "https://w3id.org/pull-berlin/ontology/"
CCO = "https://www.commoncoreontologies.org/"


class SourceKind(Enum):
    """Characteristic category of an information source (ontology: pb:SourceKind)."""

    OPEN_GEODATA = "open_geodata"
    MAPS_AND_REVIEWS = "maps_and_reviews"
    RENTAL_MARKETPLACE = "rental_marketplace"
    EVENT_LISTING = "event_listing"
    VENUE_OWN_SITE = "venue_own_site"
    OFFICIAL_COMMUNITY = "official_community"
    SOCIAL = "social"
    HUMAN_REVIEW = "human_review"  # a person checked the claim and said yes or no (data/reviews/)

    @property
    def ontology_term(self) -> str:
        return PB + "".join(part.capitalize() for part in self.value.split("_"))
