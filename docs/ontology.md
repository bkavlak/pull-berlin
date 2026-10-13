# Ontological Foundation

The domain model in `src/pull_berlin` **sits on top of** a formal ontology in `ontology/`.
The ontology answers *what kinds of things exist* in our domain; the domain model answers *how our software reasons about them*.
They are kept parallel and in sync by contract tests (see §6).

```
  ┌────────────────────────────────────────────────────────────┐
  │  Python domain model (DDD)  Space, Offering, Claim, …      │  behaviour, invariants, policies
  ├────────────────────────────────────────────────────────────┤
  │  pull-berlin ontology (pb:)  EventSpace, EventRentalRole, …  │  what our terms mean
  ├────────────────────────────────────────────────────────────┤
  │  Common Core Ontologies 2026-08-13 (cco:)                  │  Facility, Geospatial Location, City, Organization, ICE, Act of Renting …
  ├────────────────────────────────────────────────────────────┤
  │  BFO 2020 — ISO/IEC 21838-2 (obo:BFO_…)                    │  site, material entity, role, process, GDC …
  └────────────────────────────────────────────────────────────┘
        + GeoSPARQL (geo:) for geometries, PROV-O (prov:) for provenance, SKOS for classifications
```

## 1. Why these foundations

- **BFO 2020** is the ISO top-level ontology and is the one Smith & Mark's line of work grew into.
- **CCO** is the BFO-aligned mid-level suite with the geospatial pieces we need already modeled: `Geospatial Region` (a BFO site at the Earth's surface), `Geospatial Location`, `Geospatial Position` (a fiat point), `Government Domain`, `City`, `Local Administrative Region`, `Facility` and `Entertainment Facility`, `Act of Renting`, `Act of Facility Use`, `Act of Entertainment`, information entities. Its geospatial module already uses `geo:asWKT`.
- **GeoSPARQL** gives standard geometry serialization; **PROV-O** gives provenance; **SKOS** gives graded/radial classification schemes.
- Pinned copies live in `ontology/imports/` and resolve offline via `ontology/catalog-v001.xml` (Protégé, ROBOT).

## 2. Smith & Mark (1998), "Ontology and Geographic Kinds" — how each idea is applied

| Idea in the paper | Where it shows up |
|---|---|
| **Bona fide vs fiat boundaries/objects** | `pb:EnclosedEventSpace` (boundaries coincide with walls — bona fide) vs `pb:OpenAirEventSpace` (some boundary is fiat — courtyard, rooftop, beer garden). Berlin and the Bezirke are fiat objects (`pb:boundaryCharacter "fiat"`). Annotation `pb:boundaryCharacter` on every spatial class. |
| **Geographic objects are sites/regions, the "what" and "where" are intertwined** | An event space is a **BFO site** provided by a material artifact, not the building itself. The building (`cco:Facility`) is located in a `cco:Geospatial Location` and in a `pb:Bezirk`. |
| **Boundary-sensitive categorization; granularity matters** | One facility can provide several event spaces (hall + yard). Resolution and claims are made at the right grain: a review about "the big hall" is about the site, not the building. |
| **Vagueness is in concepts, not the world** | The world model is crisp OWL. Degrees live only in information entities: every `pb:Claim` carries `pb:confidence`. |
| **Radial, prototype-based categories (Rosch)** | Space types (club, bar, loft, …) are a SKOS scheme `pb:SpaceCategoryScheme` with prototype definitions, **not** an OWL subclass tree. A space falls under a category to a degree via `pb:SpaceCategoryAssignment`. These prototype definitions are also the criteria text we give Laya. |
| **Scale dependence / mesoscopic level** | Catalog stays at human (mesoscopic) scale: sites in buildings, inside Bezirke, inside Berlin. |
| **Cultural/linguistic variation of categories** | Labels are bilingual (`@de`, `@en`); categories are our classification, versioned, and may differ from Google/OSM taxonomies — adapters translate (anticorruption layer). |

## 3. Core terms (v0.1.0)

| pb term | BFO/CCO parent | Meaning (short) | Domain model type |
|---|---|---|---|
| — | `cco:Material Artifact` | the building/premises; **aggregate root** | `catalog.domain.facility.Facility` |
| `EventSpace` | `bfo:site` | site provided by a material artifact that can hold a gathering | *(pending: entity inside Facility)* |
| `EnclosedEventSpace` / `OpenAirEventSpace` | `EventSpace` | bona fide / partly fiat boundaries | *(pending)* |
| `SpaceUseRole` | `bfo:role` | the artifact is made available for some kind of planned act — **extension point** | `catalog.domain.offering.Offering` |
| `EventRentalRole` | `SpaceUseRole` | realized in `cco:Act of Renting` / `Act of Facility Use` by another agent | `OfferingKind.EVENT_RENTAL` |
| `EventHostingRole` | `SpaceUseRole` | realized in `cco:Act of Entertainment` organized by the operator | `OfferingKind.EVENT_HOSTING` |
| `TimeWindow` (`Evening`, `Night`) | `skos:Concept` | recurring daily band, classifies temporal regions | `catalog.domain.values.TimeWindow` |
| `SpaceCategory` | `skos:Concept` | radial category with prototype | `catalog.domain.values.SpaceCategory` |
| `Bezirk`, `Berlin` | `cco:Local Administrative Region`, `cco:City` | fiat administrative regions | *(pending: PostGIS assignment)* |
| `InformationSource` + `SourceKind` | `cco:ICE`, `skos:Concept` | body of published content and its category | `sourcing.domain.Source`, `shared_kernel.SourceKind` |
| `Observation` | `cco:Descriptive ICE` | what one document says about one candidate | `catalog.domain.observation.Observation` |
| `Evidence`, `UserReview` | `cco:Descriptive ICE` | excerpt supporting/opposing a claim | `catalog.domain.claim.Evidence` |
| `Claim`, `SpaceCategoryAssignment` | `cco:Descriptive ICE` | assertion with confidence, ≥1 evidence | `catalog.domain.claim.Claim` |

Relations: `pb:providesSite`/`pb:siteProvidedBy`, `pb:operates`, `pb:realizableDuring`, `pb:hasSourceKind`, `pb:fromSource`, `pb:excerptedFrom`, `pb:supportedBy`, `pb:opposedBy`, `pb:assignsCategory`, `pb:confidence`; reused: `bfo:located in`, `bfo:bearer of`/`inheres in`, `cco:is about`, `cco:designated by`, `bfo:is carrier of` + `cco:has text value` / `has URI value`, `geo:hasGeometry`/`geo:asWKT`, `prov:generatedAtTime`.

See `ontology/examples/example-space.ttl` for every pattern used once.

## 4. Modelling decisions worth knowing

1. **Roles inhere in the material artifact, not in the site.** Rentability depends on the operator's control over the building; BFO practice puts realizables in material bearers. The role is *about* the sites the artifact provides.
2. **Recurring windows are classifications, not BFO temporal regions.** "Every evening" is not one temporal region.
3. **CCO information pattern:** literal text/URIs sit on an `Information Bearing Entity` that `is carrier of` the ICE. The reasoner rejected putting `has text value` directly on ICEs — this is enforced by the shapes.
4. **`pb:excerptedFrom` instead of `bfo:continuant part of` between ICEs**: the latter is inconsistent with BFO 2020 + CCO axioms (HermiT).
5. **OWL for meaning (open world), SHACL for data completeness (closed world).** "A claim must have evidence" is a SHACL shape, not an OWL axiom.
6. **Spatial containment in Berlin** is enforced by the Python domain (point-in-polygon on the official boundary) and asserted in RDF via `bfo:located in` a `pb:Bezirk`; no spatial reasoning in OWL.
7. Namespace `https://w3id.org/pull-berlin/ontology/` is a **placeholder** until registered at w3id.org.

## 5. The ontology is the foundation: how the domain sits on it

- Every domain type/enum member that denotes something in the world MUST correspond to a pb (or CCO/BFO) term, declared in the ontology with `pb:domainModelType`, and in Python via a class-level `ONTOLOGY_TERM` IRI.
- New concepts are added **ontology first**: define the term (genus + differentia, BFO parent, label, definition), then the domain type, then the mapping test.
- Python never imports rdflib in the domain layer. RDF export is a Publishing adapter that translates domain → CCO patterns (this keeps the verbose IBE/ICE pattern out of domain code).

## 6. Quality gates

| Check | Tier | How |
|---|---|---|
| Domain → ontology mapping: every `ONTOLOGY_TERM` exists in `pull-berlin.ttl` and its `pb:domainModelType` points back | integration | `tests/integration/test_ontology_contract.py` |
| Ontology + examples consistent (HermiT), SHACL conforms, every pb class has label + definition | integration | `ontology/tools/check_ontology.py` |
| RDF export of a catalog conforms to shapes | integration | exporter test with pyshacl |
| Domain → RDF translation emits the right triples | unit | in-memory graph built from hand-made domain objects, no files |

The mapping contract reads ontology files, so it is an integration test by our rules; translation logic is unit tested with in-memory graphs.

## 7. Extension recipe (e.g. coworking)

1. Ontology: `pb:CoworkingUseRole ⊂ pb:SpaceUseRole`, realized in `cco:Act of Facility Use` for work; maybe `pb:Daytime` TimeWindow; new SpaceCategories.
2. Run `check_ontology.py`.
3. Domain: `OfferingKind.COWORKING` with `ONTOLOGY_TERM`, `OfferingPolicy` rule, ClaimTypes + Laya questions.
4. Tests in the usual pyramid order.
