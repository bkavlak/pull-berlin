from __future__ import annotations

import pytest

from pull_berlin.catalog.domain.values import TimeWindow
from pull_berlin.extraction.opening_hours import windows_from_opening_hours

EVENING, NIGHT = TimeWindow.EVENING, TimeWindow.NIGHT


@pytest.mark.parametrize(
    ("opening_hours", "expected"),
    [
        ("Mo-Su 18:00-02:00", {EVENING, NIGHT}),
        ("Fr,Sa 23:00-06:00", {EVENING, NIGHT}),
        ("Mo-Fr 10:00-20:00", {EVENING}),
        ("Mo-Fr 18:00-24:00", {EVENING}),
        ("Mo-Fr 09:00-17:00", set()),
        ("Mo-Fr 12:00-15:00,18:00-23:00", {EVENING}),
        ("Sa 20:00-03:00; Su off", {EVENING, NIGHT}),
        ("Fr 22:00-26:00", {EVENING, NIGHT}),
        ("24/7", {EVENING, NIGHT}),
        ("Th-Sa 23:00+", {EVENING, NIGHT}),
        ("Mo-Fr 08:00+", set()),
        ("Mo-Fr 9:00-17:30", set()),
        ("off", set()),
        ("closed", set()),
    ],
)
def test_known_hours_map_to_windows(opening_hours: str, expected: set[TimeWindow]) -> None:
    assert windows_from_opening_hours(opening_hours) == frozenset(expected)


@pytest.mark.parametrize("opening_hours", ["by appointment", "sunset-sunrise", "", "   "])
def test_unparseable_hours_are_unknown_not_empty(opening_hours: str) -> None:
    assert windows_from_opening_hours(opening_hours) is None
