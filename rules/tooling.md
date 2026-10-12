# OBEY Tooling Preferences

`MUST` is binding, `SHOULD` is a strong default, `MUST NOT` is forbidden.

## Runtimes and packages

1. **asdf** manages language runtimes. Versions are pinned in `.tool-versions` at the repo root.
   - `python` (project interpreter), `java` (HermiT reasoner for the ontology check), `nodejs` only if the web map ever needs a build step.
2. **uv** manages Python dependencies, virtualenvs, lockfile and tool runs.
   - Dependencies live in `pyproject.toml`; `uv.lock` is committed.
   - Add deps with `uv add <pkg>` / `uv add --dev <pkg>`; run with `uv run …`; one-off tools with `uvx …` or `uv tool install …`.
   - uv MUST use the asdf-provided interpreter (`uv venv --python "$(asdf which python)"` or `UV_PYTHON` set accordingly); uv MUST NOT download its own Python (`UV_PYTHON_DOWNLOADS=never`).
3. MUST NOT use `pip install`, `poetry`, `pipenv`, `conda`, `pyenv` or system/Homebrew Python for this project.
4. Services that are not language runtimes (PostGIS, Dekart) run as containers, defined in `compose.yaml` (added with the project skeleton).

## Geospatial stack

5. **PostGIS** (local) is the spatial store for the catalog's read model and all spatial queries (Berlin boundary containment, Bezirk assignment, proximity for resolution). The domain talks to it only through the `SpaceRepository` port.
6. **GeoSQL** (dekart-xyz/geosql, MIT) is the agent skill for spatial SQL and analysis against the local PostGIS. Install with `uv tool install geosql && geosql`, then use `/geosql …` in the agent.
7. **Dekart** (self-hosted container) renders GeoSQL results so the agent and humans can **visually check geometry** (map in the loop). Use it to validate: Berlin/Bezirk boundaries, resolution clusters, outliers, coverage per source.
8. Set `DO_NOT_TRACK=1` in the dev environment (GeoSQL/Dekart send a version check by default).
9. **MapLibre GL JS** on OSM-based tiles remains the product map in `web/`. Dekart is the analysis/QA map; they are not interchangeable.

## Quality tools (via uv)

10. `ruff` (lint + format), `mypy --strict`, `pytest` (+ markers `unit`, `integration`, `e2e`), `rdflib`/`pyshacl`/`owlready2` for the ontology gate.
