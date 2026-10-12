# OBEY Test-Driven Development and the Testing Pyramid

## Purpose

All production code in this repository is written test-first.
This file is a binding engineering policy: `MUST` is binding, `SHOULD` is a strong default, and `MUST NOT` is forbidden.
It complements `a-philosophy-of-software-design.md` and `domain-driven-design.md`; tests read in the ubiquitous language and test public behavior, not implementation detail.

---

## The Cycle (MUST)

1. **Red** – write one failing test that states one behavior in domain language.
2. **Green** – write the least production code that makes it pass.
3. **Refactor** – remove duplication and deepen modules while all tests stay green.

- No production code without a failing test that demands it.
- A bug fix MUST start with a test that reproduces the bug.
- Commit only on green.

---

## The Pyramid (MUST be enforced rigidly)

| Layer | Share of tests | Scope | Allowed I/O | Speed |
|---|---|---|---|---|
| Unit | ~80% | one unit: a domain object, a pure function, one adapter's parsing logic | **none** | < 10 ms each, whole suite < 10 s |
| Integration | ~15% | one adapter against a real dependency (SQLite file, local LLM, recorded HTTP) | real, local only | seconds |
| End-to-end | ~5% | a whole pipeline run against a small, fixed set of recorded sources | real, local only | minutes |

- Tests live in `tests/unit`, `tests/integration`, `tests/e2e` and carry the matching pytest marker.
- The pyramid shape is checked in CI: the count of unit tests MUST exceed integration + e2e combined, by a large margin.
- Tests MUST NOT hit the live internet. Remote sources are exercised through recorded fixtures only.

---

## Unit Tests Are Real Units (MUST)

A unit test:
1. Uses **only mocked or hand-built inputs**: literal values, builders, saved HTML/JSON fixture files, fakes of ports.
2. Touches **no** network, filesystem (except reading a fixture into a string), database, clock, randomness, environment variables or LLM.
3. Injects time, IDs and randomness through parameters or ports; never reads them globally.
4. Tests one behavior; its name states that behavior in domain language
   (`test_venue_without_evening_hours_is_not_an_evening_venue`).
5. Runs in any order and in parallel.

Doubles:
- Domain code depends on **ports** (abstract interfaces). Units replace ports with **fakes or stubs** written in `tests/fakes/`.
- Prefer fakes and stubs over `mock.patch`. Patching module internals couples tests to implementation and is a smell.
- MUST NOT mock the unit under test, value objects, or the domain model itself.
- Interaction assertions (`assert_called_with`) only where the interaction *is* the behavior (e.g. "rate limiter waits before second request").

Source adapters (scrapers):
- Parsing logic is a pure function `raw document -> domain candidates` and is unit tested with recorded fixtures in `tests/fixtures/<source>/`.
- Fetching is a separate port and is never exercised by unit tests.

---

## What to Test First (SHOULD)

1. Domain invariants: invalid value objects and entities cannot be created.
2. Domain rules: deduplication/merging of venues, confidence scoring, classification.
3. Anticorruption layers: translation from each source's shape into the domain model.
4. Application services orchestrating ports (with fakes).
5. Only then integration and e2e.

---

## Forbidden (MUST NOT)

- Tests that pass without the production code (tautologies).
- Sleeping, retry loops or real timeouts in unit tests.
- Snapshot tests of entire scraped pages as a substitute for behavioral assertions.
- Shared mutable state between tests.
- Skipped tests left in main without an issue reference.
- Lowering coverage of the domain package below 95% line / 90% branch.

---

## Review Checklist

- Was the test written before the code?
- Is every unit test free of I/O and globals?
- Are doubles fakes of ports rather than patches of internals?
- Does the test name read as a domain rule?
- Does the change keep the pyramid shape?
