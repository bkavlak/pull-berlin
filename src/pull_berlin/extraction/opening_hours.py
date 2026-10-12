"""Deterministic parser: OSM-style opening hours text -> evening/night windows.

Only answers what the pipeline needs, not the full opening_hours grammar. None means "cannot
tell"; an empty set means "known, and neither evening nor night".
"""

from __future__ import annotations

import re

from pull_berlin.catalog.domain.values import TimeWindow

_EVENING_START = 18 * 60
_MIDNIGHT = 24 * 60
_LATE_OPEN_END = 20 * 60  # "23:00+" at a club means "until late", so it counts as night
_TIME = r"(\d{1,2}):(\d{2})"
_RANGE = re.compile(rf"{_TIME}\s*-\s*{_TIME}|{_TIME}\+")
_CLOSED_RULE = re.compile(r"^[^0-9]*\b(off|closed)\b[^0-9]*$")


def windows_from_opening_hours(text: str) -> frozenset[TimeWindow] | None:
    normalized = text.strip().lower()
    if not normalized:
        return None
    if "24/7" in normalized:
        return frozenset({TimeWindow.EVENING, TimeWindow.NIGHT})

    windows: set[TimeWindow] = set()
    found_any = False
    for match in _RANGE.finditer(normalized):
        found_any = True
        if match.group(5) is not None:
            windows |= _open_ended(_minutes(match.group(5), match.group(6)))
        else:
            windows |= _closed_range(
                _minutes(match.group(1), match.group(2)), _minutes(match.group(3), match.group(4))
            )

    if found_any:
        return frozenset(windows)
    rules = [rule.strip() for rule in normalized.split(";") if rule.strip()]
    if rules and all(_CLOSED_RULE.match(rule) for rule in rules):
        return frozenset()
    return None


def _minutes(hours: str, minutes: str) -> int:
    return int(hours) * 60 + int(minutes)


def _closed_range(start: int, end: int) -> set[TimeWindow]:
    if end <= start:  # wraps past midnight, e.g. 20:00-03:00
        end += _MIDNIGHT
    windows = set()
    if start < _MIDNIGHT and end > _EVENING_START:
        windows.add(TimeWindow.EVENING)
    if end > _MIDNIGHT:
        windows.add(TimeWindow.NIGHT)
    return windows


def _open_ended(start: int) -> set[TimeWindow]:
    if start >= _LATE_OPEN_END:
        return {TimeWindow.EVENING, TimeWindow.NIGHT}
    if start >= _EVENING_START:
        return {TimeWindow.EVENING}
    return set()
