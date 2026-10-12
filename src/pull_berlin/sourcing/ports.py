"""Ports of the sourcing context. Application code depends on these, never on adapters."""

from __future__ import annotations

from typing import Protocol

from pull_berlin.catalog.domain.observation import Observation
from pull_berlin.sourcing.domain import FetchRequest, RawDocument, Source


class Fetcher(Protocol):
    def fetch(self, request: FetchRequest) -> RawDocument: ...


class SourceAdapter(Protocol):
    """Anticorruption layer for one source: knows its requests and its document format, nothing else."""

    @property
    def source(self) -> Source: ...

    def requests(self) -> list[FetchRequest]: ...

    def parse(self, document: RawDocument) -> list[Observation]: ...


class FetchError(RuntimeError):
    """A source could not be fetched (network, HTTP status, or missing recording when offline)."""
