# Agent and Contributor Rules

These rule files are binding for all code generation, edits and reviews in this repository:

1. [rules/a-philosophy-of-software-design.md](rules/a-philosophy-of-software-design.md) – module depth, information hiding, low complexity
2. [rules/domain-driven-design.md](rules/domain-driven-design.md) – ubiquitous language, bounded contexts, aggregates
3. [rules/test-driven-development.md](rules/test-driven-development.md) – test-first, rigid testing pyramid, real unit tests with mocked inputs only
4. [rules/ontology-foundation.md](rules/ontology-foundation.md) – BFO/CCO ontology is the foundation of the domain model (Smith & Mark geographic kinds)
5. [rules/tooling.md](rules/tooling.md) – asdf for runtimes, uv for Python packages, PostGIS + GeoSQL/Dekart for spatial work

## Project preferences (quick reference)

- Language: Python (version in `.tool-versions`), runtimes via **asdf**, packages via **uv**.
- Design: APOSD deep modules, DDD bounded contexts, TDD with a rigid pyramid; unit tests use only fakes and fixtures.
- Foundation: BFO 2020 → CCO → `pb:` ontology; domain types declare `ONTOLOGY_TERM`.
- Sources are segregated by `SourceKind`; each source is its own anticorruption adapter.
- Local models: **Laya** for typed decisions with calibrated probabilities; deterministic parsers for values.
- Spatial: **PostGIS** locally; use **/geosql** with **Dekart** to check geometry visually; **MapLibre** for the product map.
- Scope: Berlin city limits; Evening = from 18:00, Night = past 00:00; one-off runs; outputs CSV, JSON/GeoJSON, map.
- Google Maps via Playwright scraping (ToS risk accepted by owner), polite and isolated behind the `Fetcher` port.

Design docs: `docs/design.md`, `docs/ontology.md`.
