"""Value objects of the catalog. Immutable, validated at construction, compared by value."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum

PB = "https://w3id.org/pull-berlin/ontology/"

# Bounding box of the Land Berlin. A fiat region (Smith & Mark), so any rectangle is an
# approximation: points between the bbox and the Landesgrenze pass here. Sources are already
# queried by the Berlin boundary polygon; exact containment moves to PostGIS with the boundary.
_BERLIN_LAT = (52.3383, 52.6755)
_BERLIN_LON = (13.0884, 13.7611)
_EARTH_RADIUS_M = 6_371_008.8


class NotInBerlinError(ValueError):
    """Raised when something outside Berlin is offered to the catalog."""


@dataclass(frozen=True)
class GeoPoint:
    """A WGS84 position (ontology: cco:Geospatial Position, a fiat point)."""

    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat <= 90.0:
            raise ValueError(f"latitude out of range: {self.lat}")
        if not -180.0 <= self.lon <= 180.0:
            raise ValueError(f"longitude out of range: {self.lon}")

    def distance_m(self, other: GeoPoint) -> float:
        """Great-circle distance in metres (haversine)."""
        phi1, phi2 = math.radians(self.lat), math.radians(other.lat)
        d_phi = phi2 - phi1
        d_lambda = math.radians(other.lon - self.lon)
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))

    def require_in_berlin(self) -> GeoPoint:
        if not (
            _BERLIN_LAT[0] <= self.lat <= _BERLIN_LAT[1] and _BERLIN_LON[0] <= self.lon <= _BERLIN_LON[1]
        ):
            raise NotInBerlinError(f"{self.lat},{self.lon} is outside Berlin")
        return self


_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_GENERIC_WORDS = frozenset({"club", "bar", "berlin", "the", "das", "der", "die", "ev", "gmbh"})


@dataclass(frozen=True)
class SpaceName:
    """A designative name (ontology: cco:Designative Name) with a normalized form for resolution."""

    display: str
    normalized: str = field(init=False, compare=False)

    def __init__(self, raw: str) -> None:
        display = " ".join(raw.split())
        if not display:
            raise ValueError("name must not be blank")
        object.__setattr__(self, "display", display)
        object.__setattr__(self, "normalized", _normalize(display))

    def similarity(self, other: SpaceName) -> float:
        """0..1. Spacing differences ("SO36" vs "SO 36") do not count."""
        spaced = SequenceMatcher(None, self.normalized, other.normalized).ratio()
        compact = SequenceMatcher(
            None, self.normalized.replace(" ", ""), other.normalized.replace(" ", "")
        ).ratio()
        return max(spaced, compact)


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower().translate(_UMLAUTS))
    ascii_only = "".join(ch for ch in folded if not unicodedata.combining(ch))
    words = re.sub(r"[^a-z0-9]+", " ", ascii_only).split()
    meaningful = [word for word in words if word not in _GENERIC_WORDS]
    return " ".join(meaningful or words)


class TimeWindow(Enum):
    """Daily recurring band of Berlin clock time (ontology: pb:TimeWindow)."""

    EVENING = "evening"  # from 18:00
    NIGHT = "night"  # past 00:00

    @property
    def ontology_term(self) -> str:
        return PB + {"evening": "Evening", "night": "Night"}[self.value]


class SpaceCategory(Enum):
    """Prototype-based (radial) category; membership is graded via claims (ontology: pb:SpaceCategory)."""

    CLUB = "club"
    BAR = "bar"
    EVENT_HALL = "event_hall"
    LOFT = "loft"
    GALLERY = "gallery"
    RESTAURANT = "restaurant"
    CULTURAL_CENTRE = "cultural_centre"
    OTHER = "other"

    @property
    def ontology_term(self) -> str:
        local = (
            "OtherCategory"
            if self is SpaceCategory.OTHER
            else "".join(part.capitalize() for part in self.value.split("_"))
        )
        return PB + local
