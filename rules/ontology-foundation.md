# OBEY the Ontological Foundation

`MUST` is binding, `SHOULD` is a strong default, `MUST NOT` is forbidden. Details: `docs/ontology.md`.

1. The ontology in `ontology/` (BFO 2020 → CCO → pb) is the foundation of the domain model. The domain model specializes it; it MUST NOT contradict it.
2. New domain concepts are introduced **ontology first**: term with BFO/CCO parent, `rdfs:label`, `skos:definition` in genus–differentia form, `pb:domainModelType`; then the Python type with `ONTOLOGY_TERM`; then the contract test.
3. Ubiquitous language, ontology labels and Python names MUST agree. Renaming one renames all three in the same change.
4. Spatial terms MUST state their boundary character (bona fide / fiat) per Smith & Mark (1998).
5. Graded or prototype-based kinds (space categories) MUST be SKOS concepts with degrees on Claims, MUST NOT be OWL subclass trees.
6. Degrees of belief live only on information entities (Claims), never on world entities.
7. Reuse BFO/CCO terms before minting pb terms. Minting requires a short justification in the commit message.
8. `ontology/tools/check_ontology.py` MUST pass (HermiT consistency, SHACL, documentation) before merge.
9. Domain-layer code MUST NOT import rdflib; RDF is produced by a Publishing adapter.
10. Imports are pinned in `ontology/imports/`; upgrading CCO/BFO is its own change with a passing check.
