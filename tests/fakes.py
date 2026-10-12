"""Fakes of ports, shared by all tiers. In-memory, deterministic."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pull_berlin.sourcing.domain import FetchRequest, RawDocument
from pull_berlin.sourcing.ports import FetchError

FIXED_TIME = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)


class FakeFetcher:
    """Answers each request URL with a canned body and records what was asked."""

    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses
        self.requests: list[FetchRequest] = []

    def fetch(self, request: FetchRequest) -> RawDocument:
        self.requests.append(request)
        if request.url not in self._responses:
            raise FetchError(f"no canned response for {request.url}")
        return RawDocument(request.source_id, request.url, self._responses[request.url], FIXED_TIME)


def overpass_json(*elements: dict[str, object]) -> str:
    return json.dumps({"elements": list(elements)})


def osm_node(id_: int, name: str, lat: float, lon: float, **tags: str) -> dict[str, object]:
    return {"type": "node", "id": id_, "lat": lat, "lon": lon, "tags": {"name": name, **tags}}
