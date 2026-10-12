"""Applies the pyramid marker from the directory a test lives in, so every test has exactly one tier."""

from __future__ import annotations

from pathlib import Path

import pytest

_TIERS = ("unit", "integration", "e2e")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        tier = Path(str(item.fspath)).relative_to(Path(__file__).parent).parts[0]
        if tier in _TIERS:
            item.add_marker(getattr(pytest.mark, tier))
