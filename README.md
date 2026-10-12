# pull-berlin

A catalog of **Berlin spaces** built from many heterogeneous sources. It starts with spaces usable for **events in the evening and at night**: spaces you can hire for your own event, and venues that host their own programs.

- Design: [`docs/design.md`](docs/design.md)
- Ontological foundation (BFO 2020 → CCO → `pb:`): [`docs/ontology.md`](docs/ontology.md)
- Binding rules for humans and agents: [`AGENTS.md`](AGENTS.md)

Tooling: runtimes via **asdf** (`.tool-versions`), Python packages via **uv**. Spatial work runs on **PostGIS** with **GeoSQL** and **Dekart**.

## Usage

```bash
asdf install                      # runtimes from .tool-versions
uv sync                           # dependencies into .venv
uv run pull-berlin pull           # fetch sources -> data/out/facilities.{csv,json,geojson}
uv run pull-berlin pull --offline # rebuild exports from data/cache without network
uv run pull-berlin pull --all     # also keep facilities without an evening/night offering
```

`data/cache/` keeps every raw source response, so reruns are cheap and test fixtures are recorded from it.

## Checks

```bash
uv run pytest                                     # all tiers (unit / integration / e2e)
uv run python tools/check_pyramid.py              # the suite must stay a pyramid
uv run ruff check . && uv run mypy                # lint + strict types
uv run python ontology/tools/check_ontology.py    # HermiT consistency + SHACL (needs Java)
```

Status: OpenStreetMap slice works end to end. Next sources: Google Maps reviews with Laya, then rental marketplaces and event listings.

License: [MIT](LICENSE).
