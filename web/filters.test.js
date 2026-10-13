// Unit tests for the map's pure logic. Run: node --test web/
import { test } from "node:test";
import assert from "node:assert/strict";
import { toFacility, matches, countBy, markerKind, emptyFilter } from "./filters.js";

const feature = (props, coords = [13.42, 52.51]) => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: coords },
  properties: {
    id: "osm:node/1", name: "Tresor", category: "club", category_degree: 0.8,
    offerings: "event_hosting", evening: true, night: true, max_confidence: 0.8,
    websites: "https://tresorberlin.com", refs: "osm:node/1;site:tresorberlin.com", ...props,
  },
});

test("a GeoJSON feature becomes a facility with parsed offerings and refs", () => {
  const f = toFacility(feature({ offerings: "event_rental;event_hosting" }));
  assert.deepEqual([...f.offerings].sort(), ["event_hosting", "event_rental"]);
  assert.deepEqual(f.refs, ["osm:node/1", "site:tresorberlin.com"]);
  assert.deepEqual([f.lon, f.lat], [13.42, 52.51]);
});

test("empty offerings and websites parse to empty collections, not ['']", () => {
  const f = toFacility(feature({ offerings: "", websites: "" }));
  assert.equal(f.offerings.size, 0);
  assert.deepEqual(f.websites, []);
});

test("reviewers come from reviewed_by; data without the column means nobody checked it", () => {
  assert.deepEqual(toFacility(feature({ reviewed_by: "ada;grace" })).reviewedBy, ["ada", "grace"]);
  assert.deepEqual(toFacility(feature({})).reviewedBy, []);
});

test("a facility without known hours falls in the unknown time window", () => {
  const f = toFacility(feature({ evening: false, night: false }));
  assert.deepEqual([...f.windows], ["unknown"]);
});

test("the empty filter lets everything through", () => {
  assert.equal(matches(toFacility(feature({})), emptyFilter()), true);
});

test("filtering by offering keeps facilities with any selected offering", () => {
  const filter = { ...emptyFilter(), kinds: new Set(["event_rental"]) };
  assert.equal(matches(toFacility(feature({ offerings: "event_hosting" })), filter), false);
  assert.equal(matches(toFacility(feature({ offerings: "event_rental;event_hosting" })), filter), true);
});

test("filtering by night keeps only facilities known to operate past midnight", () => {
  const filter = { ...emptyFilter(), windows: new Set(["night"]) };
  assert.equal(matches(toFacility(feature({ night: false })), filter), false);
  assert.equal(matches(toFacility(feature({ night: true })), filter), true);
});

test("facilities below the minimum confidence are hidden", () => {
  const filter = { ...emptyFilter(), minConfidence: 0.9 };
  assert.equal(matches(toFacility(feature({ max_confidence: 0.8 })), filter), false);
});

test("category filter treats a missing category as uncategorised", () => {
  const filter = { ...emptyFilter(), categories: new Set(["uncategorised"]) };
  assert.equal(matches(toFacility(feature({ category: "" })), filter), true);
  assert.equal(matches(toFacility(feature({ category: "club" })), filter), false);
});

test("name search ignores case and accents", () => {
  const f = toFacility(feature({ name: "Café Größenwahn" }));
  assert.equal(matches(f, { ...emptyFilter(), query: "grossenwahn" }), false);
  assert.equal(matches(f, { ...emptyFilter(), query: "größen" }), true);
  assert.equal(matches(f, { ...emptyFilter(), query: "CAFE" }), true);
});

test("marker kind distinguishes rental, hosting and both", () => {
  assert.equal(markerKind(new Set(["event_rental"])), "rent");
  assert.equal(markerKind(new Set(["event_hosting"])), "hosting");
  assert.equal(markerKind(new Set(["event_rental", "event_hosting"])), "both");
});

test("countBy counts facilities per category for the filter chips", () => {
  const facilities = [feature({ category: "club" }), feature({ category: "club" }), feature({ category: "" })].map(toFacility);
  assert.deepEqual(countBy(facilities, (f) => f.category), new Map([["club", 2], ["uncategorised", 1]]));
});
