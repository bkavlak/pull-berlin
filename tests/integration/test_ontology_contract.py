"""Domain model <-> ontology contract (rules/ontology-foundation.md).

Integration tier: reads the ontology files from disk.
"""

from __future__ import annotations

import importlib
from enum import Enum
from pathlib import Path

import pytest
import rdflib

from pull_berlin.catalog.domain.claim import Claim, Evidence
from pull_berlin.catalog.domain.facility import Facility
from pull_berlin.catalog.domain.observation import Observation
from pull_berlin.catalog.domain.offering import Offering, OfferingKind
from pull_berlin.catalog.domain.values import SpaceCategory, TimeWindow
from pull_berlin.shared_kernel import SourceKind
from pull_berlin.sourcing.domain import Source

ONTOLOGY = Path(__file__).resolve().parents[2] / "ontology"
DOMAIN_MODEL_TYPE = rdflib.URIRef("https://w3id.org/pull-berlin/ontology/domainModelType")


@pytest.fixture(scope="module")
def graph() -> rdflib.Graph:
    g = rdflib.Graph()
    for path in [*sorted((ONTOLOGY / "imports").glob("*.ttl")), ONTOLOGY / "pull-berlin.ttl"]:
        g.parse(path)
    return g


def _terms() -> list[tuple[str, str]]:
    terms = [
        (t.__name__, t.ONTOLOGY_TERM) for t in (Facility, Observation, Evidence, Claim, Offering, Source)
    ]
    for enum in (TimeWindow, SpaceCategory, OfferingKind, SourceKind):
        terms += [(f"{enum.__name__}.{m.name}", m.ontology_term) for m in enum]
    return terms


@pytest.mark.parametrize(("python_name", "term"), _terms())
def test_every_domain_term_exists_in_the_ontology(graph: rdflib.Graph, python_name: str, term: str) -> None:
    assert (rdflib.URIRef(term), None, None) in graph, f"{python_name} -> {term} is not defined"


def test_every_domain_model_type_annotation_resolves_to_python(graph: rdflib.Graph) -> None:
    for subject, dotted in graph.subject_objects(DOMAIN_MODEL_TYPE):
        target = _resolve(str(dotted))
        declared = target.ontology_term if isinstance(target, Enum) else target.ONTOLOGY_TERM
        assert declared == str(subject), f"{dotted} declares {declared}, ontology says {subject}"


def _resolve(dotted: str) -> object:
    parts = dotted.split(".")
    for split in range(len(parts) - 1, 0, -1):
        try:
            obj: object = importlib.import_module(".".join(parts[:split]))
        except ModuleNotFoundError:
            continue
        for attribute in parts[split:]:
            obj = getattr(obj, attribute)
        return obj
    raise AssertionError(f"cannot import {dotted}")
