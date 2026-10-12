# pull-berlin — Design

Status: **draft v1, agreed in design session 2026-10-12**. Code follows this document; when they disagree, update one of them in the same change.

Binding rules: [`AGENTS.md`](../AGENTS.md) → APOSD, DDD, TDD.

---

## 1. Purpose

Build a catalog of **Berlin spaces** from many heterogeneous sources.
First use case: **spaces usable for events in the evening and at night** — both spaces you can *hire* for your own event and venues that *host* evening/night programs.

The model is built around `Space` + `Offering` so that later use cases (coworking, studios, rehearsal rooms, sports halls, …) are new `Offering` kinds, not a rewrite.

### Decisions so far

| # | Decision | Choice |
|---|---|---|
| D1 | Language & tooling | Python (pinned in `.tool-versions`); runtimes via **asdf**, packages via **uv** — see `rules/tooling.md` |
| D2 | Target venues | Both hire-able spaces and hosting venues, as separate offering kinds |
| D3 | Time windows | `Evening` = available from 18:00; `Night` = available past 00:00 |
| D4 | Geography | Berlin city limits (12 Bezirke) |
| D5 | Run mode | One-off / manual runs; catalog keeps latest state; raw fetches are cached |
| D6 | Local model | [Laya](https://github.com/NandhaKishorM/laya) (Apache-2.0) behind the `TextClassifier` port. Measured 2026-10-12: zero-shot it loses to the keyword baseline on venue-site text (F1 0.71 vs 0.81, Brier 0.236 vs 0.109), so keywords are the default until a fine-tuned Laya wins on human-reviewed labels — see `eval/README.md` |
| D7 | Google Maps | Signed-out Google Maps shows a *limited view* without reviews (verified 2026-10-12), so scraping reviews is not possible without a Google login. Parked; venue websites are used for free text instead. Options: owner's own login, Places API (5 reviews/place), other review sites |
| D8 | Output | CSV, JSON (+ GeoJSON), and a MapLibre web map on OSM-based tiles (product). Dekart via GeoSQL for analysis/QA maps |
| D9 | First slice | OSM Overpass (base list) + Google Maps reviews (enrichment via Laya) |
| D10 | Foundation | Parallel formal ontology: BFO 2020 → CCO → `pb:` with GeoSPARQL/PROV/SKOS, applying Smith & Mark (1998). Domain model specializes it. See [`ontology.md`](ontology.md) |
| D11 | Spatial store | Local **PostGIS** behind `SpaceRepository` (replaces SQLite). Enables containment, Bezirk assignment, proximity search, and GeoSQL |
| D12 | Map in the loop | **GeoSQL** agent skill + self-hosted **Dekart** to render query results and catch geometry errors visually |
| D13 | Aggregate root | **Facility** (cco:Material Artifact) is the aggregate root; sources describe facilities, offerings are its roles. Event Spaces become entities inside it when a source distinguishes them |

---

## 2. Ubiquitous Language

Each term below is defined formally in `ontology/pull-berlin.ttl`; the table in [`ontology.md` §3](ontology.md#3-core-terms-v010) gives the BFO/CCO parent of each.

| Term | Meaning |
|---|---|
| **Space** | An event space: a *site* (hall, floor, courtyard) provided by a building or other artifact in Berlin. Enclosed (bona fide boundaries) or open-air (partly fiat). Identity: our `SpaceId`. Aggregate root. |
| **Facility** | The material thing (building, boat, arch) that provides one or more Spaces and is operated by an Agent. |
| **Offering** | A way a Space can be used (ontologically a *Space Use Role* of its Facility). Kind + time windows + optional terms. A Space has 0..n Offerings. |
| **OfferingKind** | `EVENT_HIRE` (you can book the space for your own event), `EVENT_HOSTING` (the space runs its own evening/night program). Extensible enum. |
| **TimeWindow** | `EVENING` (≥18:00) or `NIGHT` (past 00:00), derived from opening hours or claims. |
| **Source** | A place information comes from (e.g. *OSM Overpass*, *Google Maps*). Has a `SourceKind` and a reliability prior. |
| **SourceKind** | Characteristic category of a source — see §4. |
| **RawDocument** | Exactly what a source returned (HTML/JSON + URL + fetched-at). Immutable, cached. |
| **Observation** | A source's statement about one Space-like thing: name, location, attributes, texts. Produced by a source adapter from a RawDocument. |
| **Evidence** | A piece of text or field in an Observation that supports a Claim (e.g. one Google review). Always points back to its Source and URL. |
| **SpaceCategory** | A prototype-based (radial) category such as club or loft; Spaces fall under it to a degree. |
| **Claim** | A typed assertion about a Space, e.g. `is_hireable_for_private_events`, `space_type=club`, `capacity_band=100-300`, `operates_past_midnight`. Carries a probability and its Evidence. |
| **Confidence** | The catalog's combined belief in a Claim across all Evidence, using source priors and classifier probabilities. |
| **Resolution** | Deciding that two Observations describe the same Space. |
| **Catalog** | The set of resolved Spaces with their Offerings and Claims. |

Code, tests and docs MUST use these words. "Venue" is allowed only in user-facing text as a synonym of Space.

---

## 3. Bounded Contexts and Context Map

```
 ┌────────────┐  RawDocument   ┌──────────────┐  Observation+Evidence  ┌──────────────┐  Claims   ┌─────────────────┐  Spaces  ┌─────────────┐
 │  Sourcing  │ ─────────────▶ │  Adapters    │ ─────────────────────▶ │  Extraction  │ ────────▶ │ Catalog (CORE)  │ ───────▶ │ Publishing  │
 │ fetch,cache│                │ (ACL / source)│                        │ Laya+parsers │           │ resolve, merge, │          │ csv/json/   │
 └────────────┘                └──────────────┘                        └──────────────┘           │ confidence      │          │ geojson/map │
                                                                                                   └─────────────────┘          └─────────────┘
```

| Context | Type | Responsibility | Talks to others via |
|---|---|---|---|
| **Sourcing** | generic | Fetching politely (rate limit, robots, retries), raw cache, source registry | emits `RawDocument` |
| **Source adapters** | anticorruption layer, one per source | Translate one source's shape into `Observation`s. Pure parsing. | consumes `RawDocument`, emits `Observation` |
| **Extraction** | supporting | Turn Evidence text into typed `Claim`s: Laya for decisions, deterministic parsers for values (capacity numbers, prices, phone, opening hours) | `ClaimClassifier`, `ValueParser` ports |
| **Catalog** | **core domain** | Space aggregate, Offering derivation, Resolution, Confidence | `SpaceRepository` port |
| **Publishing** | generic | Exports (CSV/JSON/GeoJSON/RDF), the MapLibre map, PostGIS read-model tables for GeoSQL/Dekart | reads Catalog |

Rules:
- Only adapters know a source's HTML/JSON. Nothing outside an adapter imports a source's vocabulary.
- Catalog never knows which source or model produced a Claim beyond `SourceKind`, source id and probability.
- Laya is an implementation detail of the `ClaimClassifier` port.

---

## 4. Source Catalog (segregated by SourceKind)

Every source is registered with: `id`, `SourceKind`, `reliability_prior` per claim type, access method, legal notes, status.

| SourceKind | What it tells us best | Berlin sources (candidates) | Access | Status |
|---|---|---|---|---|
| `OPEN_GEODATA` | existence, location, category, opening hours | **OpenStreetMap Overpass** (`amenity=nightclub|bar|pub|events_venue|community_centre|arts_centre|theatre|music_venue`, …) | public API, ODbL | **slice 1** |
| `MAPS_AND_REVIEWS` | lived experience: "we rented the back room", vibe, real hours, crowd size | **Google Maps** (reviews, hours, categories), Foursquare, Yelp | Playwright scraping (Google), APIs | **slice 1** (Google) |
| `RENTAL_MARKETPLACE` | explicit hireability, capacity, price | Spacebase, eventlocation directories, Partyraum sites, Peerspace-like | HTML scraping | later |
| `EVENT_LISTING` | hosting evidence: night events actually happen there | Resident Advisor Berlin, visitBerlin / berlin.de, Tip Berlin, Exberliner, Eventbrite, Meetup | HTML/JSON | later |
| `VENUE_OWN_SITE` | authoritative terms: "Location mieten", "Private Events", capacity, contact | the Space's website, discovered via other sources | crawl 1–2 levels | later |
| `OFFICIAL_COMMUNITY` | legitimacy, scene membership | Clubcommission Berlin members, daten.berlin.de | HTML/CSV | later |
| `SOCIAL` | recency, events | Instagram, Facebook events | hard; ToS | parked |

Creative signals we deliberately want:
- **Google reviews** classified by Laya for hire/private-event mentions, late operation, capacity hints.
- **Event listings as hosting proof** — an RA event at 23:00 is strong `NIGHT` + `EVENT_HOSTING` evidence.
- **Venue-site keyword pages** (`/mieten`, `/location`, `/private-events`, `/booking`) found by crawling outward from known Spaces.
- Disagreement between sources is information (e.g. OSM says closed at 22:00, reviews talk about 4am) — Confidence handles it, nobody overwrites.

---

## 5. Domain Model (Catalog, core)

```
Space (aggregate root)
  id: SpaceId
  name: SpaceName              (value object; normalized form for resolution)
  location: GeoPoint           (value object; must lie inside Berlin boundary)
  address: Address | None
  external_refs: set[ExternalRef]   (source id + source-local id, e.g. osm:node/123, gmaps:ChIJ…)
  claims: ClaimSet             (Claims grouped by ClaimType, each with Evidence list)
  offerings() -> list[Offering]     (DERIVED from claims, never set by hand)

Offering (value object)
  kind: OfferingKind           (EVENT_HIRE | EVENT_HOSTING | … future)
  windows: frozenset[TimeWindow]
  confidence: Confidence
  terms: OfferingTerms | None  (capacity, price hints, contact)

Claim (value object)
  type: ClaimType
  value: bool | str | int | range
  evidence: tuple[Evidence, ...]
  confidence: Confidence       (computed by ConfidencePolicy)
```

Domain services / policies:
- `ResolutionPolicy` — same Space if `ExternalRef` matches, else normalized-name similarity ≥ threshold **and** distance ≤ 75 m (tunable, tested by scenarios).
- `ConfidencePolicy` — per claim: combine evidence as independent noisy-OR of `source_prior(kind, claim_type) × classifier_probability`; contradicting evidence reduces it. Pure function.
- `OfferingPolicy` — derives Offerings: e.g. `EVENT_HIRE` if `is_hireable_for_private_events` confidence ≥ τ; windows from opening hours and `operates_past_midnight`.

Invariants (tested first):
- A Space has a location inside the Berlin boundary.
- A Claim without Evidence cannot exist.
- An Offering cannot be created directly from outside the aggregate.
- Merging two Spaces unions refs and evidence; it never drops evidence.

---

## 6. Extraction with Laya

Laya (`laya` on PyPI, Apache-2.0) answers typed questions over a text in one forward pass with calibrated probabilities; `laya-multilingual` handles German, up to 8k tokens.

- **Port:** `ClaimClassifier.classify(evidence: Evidence, questions: QuestionSet) -> list[Claim]`
- **Adapter:** `LayaClaimClassifier` (uses `laya.Router`, `model="multilingual"` because Berlin text is mixed DE/EN).
- **QuestionSet v1** (domain-owned, not Laya-owned):

| ClaimType | Laya type | Question |
|---|---|---|
| `is_hireable_for_private_events` | noul | Can this space be rented or booked for a private event or party? |
| `hosts_evening_events` | noul | Does this place host its own events in the evening? |
| `operates_past_midnight` | noul | Is this place open or used after midnight? |
| `space_type` | choice | club / bar / event_hall / loft / gallery / restaurant / cultural_centre / other |
| `capacity_band` | choice | <50 / 50–150 / 150–500 / >500 / unknown |

- **Values Laya cannot extract** (numbers, prices, phone, hours strings) → deterministic `ValueParser`s (regex + `opening_hours` parsing), unit tested.
- **Accuracy loop:** `eval/gold/*.jsonl` hand-labelled Berlin snippets → `make eval` reports precision/recall per ClaimType and calibration. Later: fine-tune Laya on the gold set (their notebook/MPS script). Model choice is driven by these numbers, not by feel.
- Laya runs only in integration tests and real runs; unit tests use `FakeClaimClassifier`.

---

## 7. Pipeline (application layer)

```
discover(source)            → list[SourceTarget]          e.g. Overpass query for Berlin bbox
fetch(target)               → RawDocument                 Fetcher port (HTTP | Playwright), cached on disk
adapt(raw)                  → list[Observation]           pure, per source
extract(observation)        → list[Claim]                 ClaimClassifier + ValueParsers
resolve_and_merge(claims)   → Catalog                     domain
publish(catalog)            → csv, json, geojson          Publishing
```

Each step is an application service depending only on ports. A run is `pull-berlin run --sources osm,gmaps`. Because runs are one-off, the raw cache makes reruns cheap and doubles as the recorder for test fixtures.

Google Maps slice specifically: for each OSM-derived Space, search Google Maps by name + address, take the best match within 75 m, open the reviews panel, collect up to N reviews (configurable), polite delays, single browser context. Matching produces an `ExternalRef(gmaps, place_id)`.

---

## 8. Package Layout

```
pull-berlin/
  AGENTS.md  CLAUDE.md  rules/  docs/
  ontology/                             pull-berlin.ttl, berlin-regions.ttl, shapes/, examples/, imports/ (BFO, CCO), tools/check_ontology.py
  pyproject.toml                        uv, ruff, mypy --strict, pytest
  src/pull_berlin/
    catalog/          domain/   (each type declares ONTOLOGY_TERM) (space.py, offering.py, claim.py, values.py, policies/)  ports.py
    extraction/       domain/ (question_set.py, parsers/)  ports.py  adapters/laya_classifier.py
    sourcing/         domain/ (source.py, source_kind.py, raw_document.py)  ports.py  adapters/ (http_fetcher.py, playwright_fetcher.py, disk_cache.py)
    sources/          osm_overpass/ (discover.py, adapter.py)   google_maps/ (discover.py, adapter.py)   ← one package per source = one ACL
    publishing/       csv_export.py  json_export.py  geojson_export.py  rdf_export.py (domain → CCO patterns, validated by SHACL)
    application/      run_pipeline.py
    cli.py
  web/                index.html + MapLibre GL JS reading spaces.geojson (OSM-based tiles, attribution)
  tests/
    unit/  integration/  e2e/  fakes/  fixtures/<source>/
  eval/
    gold/  run_eval.py
```

Adding a source = new package under `sources/` + registry entry + fixtures. Adding a space use case = new `OfferingKind`, ClaimTypes, questions and an `OfferingPolicy` rule. Nothing else moves.

---

## 9. Testing Strategy (per `rules/test-driven-development.md`)

- **Unit (~80%)**: value objects, aggregate invariants, policies (resolution, confidence, offering derivation), each source adapter's parsing on recorded fixtures, value parsers, application services with fakes (`FakeFetcher`, `FakeClaimClassifier`, `InMemorySpaceRepository`).
- **Integration (~15%)**: PostGIS repository against a local PostGIS container; Laya adapter against the real model on a few snippets; disk cache; Playwright fetcher against a local static HTML server; exporters writing files.
- **E2E (~5%)**: full run over a recorded mini-Berlin (≈10 OSM elements + their recorded Google pages) → asserted CSV/GeoJSON.
- No live internet in any test. A separate `make record` refreshes fixtures deliberately.

---

## 10. Milestones

0. **Ontology v0.1** — ✅ core terms, Berlin regions, shapes, example, quality gate.
1. ✅ **Skeleton** — `.tool-versions` (asdf), `pyproject.toml` + `uv.lock` (uv), `compose.yaml` (PostGIS, Dekart), CI with pyramid check + ontology check, empty contexts.
2. ✅ **Catalog core** — value objects, Space, Claim, ConfidencePolicy, OfferingPolicy, ResolutionPolicy (all unit tested).
3. ✅ **OSM slice** — Overpass adapter, opening-hours → TimeWindow, export CSV/JSON/GeoJSON. First run (2026-10-12): 3,339 OSM objects → 3,309 facilities → 530 with an evening/night offering.
4. ✅ **Map** — `web/index.html` (MapLibre + OpenFreeMap): filters for offering, time window, category, confidence and name; `pull-berlin serve`. Still open: GeoSQL + Dekart QA views once PostGIS lands.
5. ✅ **Venue websites + extraction** — VenueSiteSource, QuestionSet v1, keyword baseline, Laya adapter with lexical gate, classification cache, eval tooling, silver set (50 passages).
6. **Laya fine-tuning** — human-reviewed labels (a few hundred passages), fine-tune on Apple Silicon, adopt if it beats keywords.
7. **Google Maps reviews** — only with one of the D7 options.
8. Next sources: Resident Advisor (hosting evidence), Spacebase (hire evidence).

---

## 11. Open Questions

- Confidence threshold τ for showing an Offering on the map (start 0.6, tune with eval).
- Max reviews per place for Google (start 30).
- Map tiles: raw OSM raster tiles (fine for local use, attribution required) vs OpenFreeMap vector tiles.
- Container runtime for PostGIS/Dekart: Docker Desktop, OrbStack or Colima?
- Laya on your Mac: Apple Silicon (MPS) assumed.
