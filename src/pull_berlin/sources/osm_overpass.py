"""OpenStreetMap via Overpass: the anticorruption layer for OSM tags.

All OSM vocabulary (amenity=…, opening_hours, contact:website) stays in this module. Outward it
speaks only catalog language: Observations carrying Statements with Evidence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pull_berlin.catalog.domain.claim import ClaimType, Evidence, Proposition, Stance, Statement
from pull_berlin.catalog.domain.observation import Observation
from pull_berlin.catalog.domain.values import GeoPoint, SpaceCategory, SpaceName, TimeWindow
from pull_berlin.extraction.opening_hours import windows_from_opening_hours
from pull_berlin.shared_kernel import SourceKind
from pull_berlin.sourcing.domain import FetchRequest, RawDocument, Source

ENDPOINT = "https://overpass-api.de/api/interpreter"

_YES = ClaimType
_C = SpaceCategory

# amenity value -> what that tag says, and how strongly. Strength 1.0 = the tag's definition says so.
_AMENITY_STATEMENTS: Mapping[str, tuple[tuple[Proposition, float], ...]] = {
    "nightclub": (
        (Proposition(_YES.HOSTS_EVENING_EVENTS), 1.0),
        (Proposition(_YES.OPERATES_PAST_MIDNIGHT), 0.9),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.CLUB), 1.0),
    ),
    "bar": (
        (Proposition(_YES.OPERATES_IN_EVENING), 0.9),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.BAR), 1.0),
    ),
    "pub": (
        (Proposition(_YES.OPERATES_IN_EVENING), 0.9),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.BAR), 0.8),
    ),
    "events_venue": (
        (Proposition(_YES.IS_RENTABLE_FOR_PRIVATE_EVENTS), 1.0),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.EVENT_HALL), 1.0),
    ),
    "music_venue": (
        (Proposition(_YES.HOSTS_EVENING_EVENTS), 1.0),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.CLUB), 0.6),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.CULTURAL_CENTRE), 0.4),
    ),
    "theatre": (
        (Proposition(_YES.HOSTS_EVENING_EVENTS), 0.9),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.CULTURAL_CENTRE), 0.8),
    ),
    "arts_centre": (
        (Proposition(_YES.HOSTS_EVENING_EVENTS), 0.7),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.CULTURAL_CENTRE), 1.0),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.GALLERY), 0.4),
    ),
    "community_centre": (
        (Proposition(_YES.IS_RENTABLE_FOR_PRIVATE_EVENTS), 0.6),
        (Proposition(_YES.FALLS_UNDER_CATEGORY, _C.CULTURAL_CENTRE), 0.6),
    ),
}

# Tags on any amenity that say live events happen there. Values other than "no" count (music_genre=jazz).
_EVENT_TAGS: Mapping[str, float] = {"live_music": 0.9, "nightclub": 0.8, "karaoke": 0.7, "music_genre": 0.6}

# Known hours that do not reach a window are evidence against it, a bit weaker than for it.
_HOURS_OPPOSITION_STRENGTH = 0.8
_WINDOW_CLAIMS = {TimeWindow.EVENING: _YES.OPERATES_IN_EVENING, TimeWindow.NIGHT: _YES.OPERATES_PAST_MIDNIGHT}

_QUERY = """[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="4"]["name"="Berlin"]->.berlin;
nwr["amenity"~"^({amenities})$"]["name"](area.berlin);
out center tags;"""


class OsmOverpassSource:
    def __init__(self, endpoint: str = ENDPOINT) -> None:
        self._endpoint = endpoint
        self._source = Source(id="osm", kind=SourceKind.OPEN_GEODATA, name="OpenStreetMap (Overpass API)")

    @property
    def source(self) -> Source:
        return self._source

    def requests(self) -> list[FetchRequest]:
        query = _QUERY.format(amenities="|".join(sorted(_AMENITY_STATEMENTS)))
        return [
            FetchRequest(
                source_id=self._source.id, url=self._endpoint, method="POST", form=(("data", query),)
            )
        ]

    def parse(self, document: RawDocument) -> list[Observation]:
        try:
            elements = json.loads(document.content)["elements"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise ValueError(f"not an Overpass JSON response from {document.url}") from error
        return [obs for element in elements if (obs := self._observe(element)) is not None]

    def _observe(self, element: Mapping[str, Any]) -> Observation | None:
        tags: Mapping[str, str] = element.get("tags", {})
        position = element.get("center", element)
        name = tags.get("name", "").strip()
        if not name or "lat" not in position or "lon" not in position:
            return None

        local_id = f"{element['type']}/{element['id']}"
        url = f"https://www.openstreetmap.org/{local_id}"
        return Observation(
            source_id=self._source.id,
            source_kind=self._source.kind,
            local_id=local_id,
            url=url,
            name=SpaceName(name),
            location=GeoPoint(lat=float(position["lat"]), lon=float(position["lon"])),
            website=tags.get("website") or tags.get("contact:website"),
            statements=self._statements(tags, url),
        )

    def _statements(self, tags: Mapping[str, str], url: str) -> tuple[Statement, ...]:
        statements = []
        amenity = tags.get("amenity", "")
        for proposition, strength in _AMENITY_STATEMENTS.get(amenity, ()):
            statements.append(Statement(proposition, self._evidence(url, f"amenity={amenity}", strength)))

        for key, strength in _EVENT_TAGS.items():
            value = tags.get(key, "")
            if value and value != "no":
                evidence = self._evidence(url, f"{key}={value}", strength)
                statements.append(Statement(Proposition(_YES.HOSTS_EVENING_EVENTS), evidence))

        hours = tags.get("opening_hours", "")
        windows = windows_from_opening_hours(hours) if hours else None
        if windows is not None:
            for window, claim_type in _WINDOW_CLAIMS.items():
                stance = Stance.SUPPORTS if window in windows else Stance.OPPOSES
                strength = 1.0 if stance is Stance.SUPPORTS else _HOURS_OPPOSITION_STRENGTH
                excerpt = f"opening_hours={hours}"
                statements.append(
                    Statement(Proposition(claim_type), self._evidence(url, excerpt, strength, stance))
                )
        return tuple(statements)

    def _evidence(
        self, url: str, excerpt: str, strength: float, stance: Stance = Stance.SUPPORTS
    ) -> Evidence:
        return Evidence(
            source_id=self._source.id,
            source_kind=self._source.kind,
            url=url,
            excerpt=excerpt,
            strength=strength,
            stance=stance,
        )
