"""Ontology quality gate (integration tier: uses files and a Java reasoner).

    uv run --with rdflib --with pyshacl --with owlready2 python ontology/tools/check_ontology.py

1. Parses BFO + CCO imports and the pull-berlin modules.
2. HermiT: ontology alone, and ontology + every example, must be consistent.
3. SHACL: every example must conform to the shapes.
4. Every class in the pb namespace must have rdfs:label and skos:definition.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import owlready2
import pyshacl
import rdflib
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parents[1]
PB = "https://w3id.org/pull-berlin/ontology/"
HERMIT = Path(owlready2.__file__).parent / "hermit"


def load(paths: list[Path]) -> rdflib.Graph:
    graph = rdflib.Graph()
    for path in paths:
        graph.parse(path)
    return graph


def is_consistent(graph: rdflib.Graph) -> bool:
    """HermiT cannot read owl:imports to remote IRIs or GeoSPARQL literals; both are stripped first."""
    reasoned = rdflib.Graph() + graph
    reasoned.remove((None, OWL.imports, None))
    for s, p, o in list(reasoned):
        if isinstance(o, rdflib.Literal) and o.datatype and "opengis" in str(o.datatype):
            reasoned.remove((s, p, o))
    with tempfile.NamedTemporaryFile(suffix=".owl", delete=False) as handle:
        reasoned.serialize(handle.name, format="xml")
    result = subprocess.run(
        [
            "java",
            "-Xmx2000M",
            "-cp",
            f"{HERMIT}{os.pathsep}{HERMIT / 'HermiT.jar'}",
            "org.semanticweb.HermiT.cli.CommandLine",
            "-c",
            "-I",
            f"file://{handle.name}",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def undocumented_classes(graph: rdflib.Graph) -> list[str]:
    return [
        str(cls)
        for cls in graph.subjects(RDF.type, OWL.Class)
        if str(cls).startswith(PB)
        and (graph.value(cls, RDFS.label) is None or graph.value(cls, SKOS.definition) is None)
    ]


def main() -> int:
    ontology = load(
        [*sorted((ROOT / "imports").glob("*.ttl")), ROOT / "pull-berlin.ttl", ROOT / "berlin-regions.ttl"]
    )
    shapes = load([ROOT / "shapes" / "pull-berlin-shapes.ttl"])
    failures: list[str] = []

    if not is_consistent(ontology):
        failures.append("ontology is inconsistent")
    failures += [f"class without label/definition: {c}" for c in undocumented_classes(ontology)]

    for example in sorted((ROOT / "examples").glob("*.ttl")):
        data = load([example])
        if not is_consistent(ontology + data):
            failures.append(f"{example.name}: inconsistent with ontology")
        conforms, _, report = pyshacl.validate(
            data, shacl_graph=shapes, ont_graph=ontology, inference="rdfs", advanced=True
        )
        if not conforms:
            failures.append(f"{example.name}: SHACL violations\n{report}")

    for failure in failures:
        print("FAIL", failure)
    print("ontology check:", "FAILED" if failures else "OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
