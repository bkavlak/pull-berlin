"""Decides which observed facilities are the same thing, and merges them."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from functools import reduce

from pull_berlin.catalog.domain.facility import ExternalRef, Facility

_METRES_PER_DEGREE_LAT = 111_320.0


class ResolutionPolicy:
    """Same facility iff they share an external reference, or their names are similar enough and
    they are close enough. Transitive (union-find), O(n) via a spatial grid."""

    def __init__(self, max_distance_m: float = 75.0, min_name_similarity: float = 0.85) -> None:
        self.max_distance_m = max_distance_m
        self.min_name_similarity = min_name_similarity

    def resolve(self, facilities: Iterable[Facility]) -> list[Facility]:
        items = list(facilities)
        groups = _UnionFind(len(items))

        first_with_ref: dict[ExternalRef, int] = {}
        for index, item in enumerate(items):
            for ref in item.refs:
                groups.union(index, first_with_ref.setdefault(ref, index))

        for a, b in self._nearby_pairs(items):
            if self._looks_same(items[a], items[b]):
                groups.union(a, b)

        merged = [reduce(Facility.merge, (items[i] for i in members)) for members in groups.members()]
        return sorted(merged, key=lambda f: f.id)

    def _looks_same(self, a: Facility, b: Facility) -> bool:
        return (
            a.location.distance_m(b.location) <= self.max_distance_m
            and a.name.similarity(b.name) >= self.min_name_similarity
        )

    def _nearby_pairs(self, items: list[Facility]) -> Iterable[tuple[int, int]]:
        cell_lat = self.max_distance_m / _METRES_PER_DEGREE_LAT
        cells: dict[tuple[int, int], list[int]] = defaultdict(list)
        keys = []
        for index, item in enumerate(items):
            cell_lon = cell_lat / max(math.cos(math.radians(item.location.lat)), 0.01)
            key = (math.floor(item.location.lat / cell_lat), math.floor(item.location.lon / cell_lon))
            cells[key].append(index)
            keys.append(key)
        for index, (row, col) in enumerate(keys):
            for d_row in (-1, 0, 1):
                for d_col in (-1, 0, 1):
                    for other in cells.get((row + d_row, col + d_col), ()):
                        if other > index:
                            yield index, other


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        self._parent[self.find(a)] = self.find(b)

    def members(self) -> list[list[int]]:
        groups: dict[int, list[int]] = defaultdict(list)
        for x in range(len(self._parent)):
            groups[self.find(x)].append(x)
        return list(groups.values())
