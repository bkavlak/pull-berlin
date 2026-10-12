from __future__ import annotations

from pathlib import Path

import pytest

from pull_berlin.sourcing.adapters import CachingFetcher
from pull_berlin.sourcing.domain import FetchRequest
from pull_berlin.sourcing.ports import FetchError

from ..fakes import FakeFetcher

REQUEST = FetchRequest(source_id="osm", url="https://example.org/q", method="POST", form=(("data", "query"),))


def test_first_fetch_goes_to_the_network_and_is_stored(tmp_path: Path) -> None:
    inner = FakeFetcher({REQUEST.url: "payload"})
    CachingFetcher(tmp_path, inner).fetch(REQUEST)
    assert len(inner.requests) == 1
    assert list((tmp_path / "osm").glob("*.json"))


def test_second_fetch_is_served_from_disk(tmp_path: Path) -> None:
    inner = FakeFetcher({REQUEST.url: "payload"})
    CachingFetcher(tmp_path, inner).fetch(REQUEST)
    document = CachingFetcher(tmp_path, inner).fetch(REQUEST)
    assert len(inner.requests) == 1
    assert document.content == "payload"


def test_replayed_document_keeps_its_original_fetch_time(tmp_path: Path) -> None:
    first = CachingFetcher(tmp_path, FakeFetcher({REQUEST.url: "p"})).fetch(REQUEST)
    replayed = CachingFetcher(tmp_path, None).fetch(REQUEST)
    assert replayed.fetched_at == first.fetched_at


def test_offline_cache_miss_is_a_fetch_error(tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="offline"):
        CachingFetcher(tmp_path, None).fetch(REQUEST)
