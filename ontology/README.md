# ontology/

| path | what |
|---|---|
| `pull-berlin.ttl` | core OWL ontology (pb:) on BFO 2020 + CCO 2026-08-13 |
| `berlin-regions.ttl` | Berlin and its 12 Bezirke as fiat regions |
| `shapes/pull-berlin-shapes.ttl` | SHACL shapes for published data |
| `examples/*.ttl` | worked examples; each must be consistent and conform |
| `imports/` | pinned BFO and CCO modules (BSD-3 / CC-BY) |
| `catalog-v001.xml` | maps import IRIs to local files for Protégé/ROBOT |
| `tools/check_ontology.py` | quality gate |

Open `pull-berlin.ttl` in Protégé (catalog is picked up automatically).
Check: `uv run --with rdflib --with pyshacl --with owlready2 python ontology/tools/check_ontology.py` (needs Java).
Explanation and design decisions: `../docs/ontology.md`.
