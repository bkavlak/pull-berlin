"""Sourcing context: which sources exist and what fetching them returns."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from pull_berlin.shared_kernel import PB, SourceKind


@dataclass(frozen=True)
class Source:
    """An information source (ontology: pb:InformationSource)."""

    ONTOLOGY_TERM = PB + "InformationSource"

    id: str
    kind: SourceKind
    name: str


@dataclass(frozen=True)
class FetchRequest:
    source_id: str
    url: str
    method: str = "GET"
    form: tuple[tuple[str, str], ...] = field(default=())  # sent url-encoded as the POST body
    headers: tuple[tuple[str, str], ...] = field(default=())
    timeout_s: float | None = None  # how long this request may take; not part of its identity
    retries: int | None = None  # how often a transient failure is retried; not part of its identity
    remember_failure: bool = False  # optional sources: a failure is cached so reruns skip it

    @property
    def fingerprint(self) -> str:
        """Stable identity of the request; the raw cache is keyed by it."""
        material = "\n".join(
            [
                self.method,
                self.url,
                *(f"{k}={v}" for k, v in self.form),
                *(f"{k}:{v}" for k, v in sorted(self.headers)),
            ]
        )
        return hashlib.sha256(material.encode()).hexdigest()


@dataclass(frozen=True)
class RawDocument:
    """Exactly what a source returned. Immutable; the only input source adapters parse."""

    source_id: str
    url: str
    content: str
    fetched_at: datetime
