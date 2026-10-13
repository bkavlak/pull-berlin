# pull-berlin

A catalog of **Berlin spaces** built from many heterogeneous sources. It starts with spaces usable for **events in the evening and at night**: spaces you can hire for your own event, and venues that host their own programs.

**Map: https://bkavlak.github.io/pull-berlin/** · **Help check the data: [CONTRIBUTING.md](CONTRIBUTING.md)** — open this repo in any AI coding agent and say *"I want to review Berlin venues"*.

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
uv run pull-berlin pull --sites   # also read each facility's own website (keyword classifier)
uv sync --extra laya && uv run pull-berlin pull --sites --classifier laya   # Laya instead (see eval/)
uv run pull-berlin publish        # map data = data/catalog snapshot + data/reviews -> data/published
uv run pull-berlin serve          # map at http://127.0.0.1:8000/ (reads data/published, like GitHub Pages)
uv run pull-berlin review next --reviewer <login>   # human review, see skills/review-venues/SKILL.md
```

`data/cache/` keeps every raw source response, so reruns are cheap and test fixtures are recorded from it.

### How the public map is made

```
pull-berlin pull --sites --out data/catalog   (owner, occasionally)  -> data/catalog/facilities.json  (committed snapshot)
pull-berlin review record                     (contributors, via PR) -> data/reviews/<login>.jsonl    (committed)
pull-berlin publish                           (GitHub Actions on main) -> GitHub Pages
```

The snapshot holds every claim with its evidence, so publishing needs no network. Human reviews are
evidence of kind `human_review` (prior 0.98) and go through the same confidence policy as every
other source. Refresh the snapshot with `uv run pull-berlin pull --sites --out data/catalog`, then commit
only `data/catalog/facilities.json` (the other exports there are ignored). Reviews of facilities that
drop out of a new snapshot are reported by `pull-berlin review check` and otherwise ignored.

One-time GitHub setup: Settings → Pages → Source: **GitHub Actions**.

## Checks

```bash
uv run pytest                                     # all tiers (unit / integration / e2e)
uv run python tools/check_pyramid.py              # the suite must stay a pyramid
uv run ruff check . && uv run mypy                # lint + strict types
uv run python ontology/tools/check_ontology.py    # HermiT consistency + SHACL (needs Java)
node --test web/*.test.js                         # map filter logic
```

Status: OpenStreetMap + venue websites work end to end, with a filterable map (`web/`). Laya is integrated and evaluated (`eval/README.md`); zero-shot it does not yet beat the keyword baseline, so fine-tuning on reviewed labels is next.

License: [MIT](LICENSE).
