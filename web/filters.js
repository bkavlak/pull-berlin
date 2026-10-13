// Pure logic of the map: turning exported features into facilities and deciding what is shown.
// No DOM, no map library — unit tested with `node --test web/*.test.js`.

export const OFFERING_LABELS = { event_hire: "Can be hired", event_hosting: "Hosts own events" };
export const WINDOW_LABELS = { evening: "Evening (from 18:00)", night: "Night (past midnight)", unknown: "Hours unknown" };
export const UNCATEGORISED = "uncategorised";

const split = (value) => (value ? String(value).split(";").filter(Boolean) : []);

export function toFacility(feature) {
  const p = feature.properties;
  const windows = new Set();
  if (p.evening) windows.add("evening");
  if (p.night) windows.add("night");
  if (!windows.size) windows.add("unknown");
  const [lon, lat] = feature.geometry.coordinates;
  return {
    id: p.id,
    name: p.name,
    search: normalize(p.name),
    category: p.category || UNCATEGORISED,
    categoryDegree: Number(p.category_degree) || 0,
    offerings: new Set(split(p.offerings)),
    windows,
    confidence: Number(p.max_confidence) || 0,
    websites: split(p.websites),
    refs: split(p.refs),
    reviewedBy: split(p.reviewed_by),
    lon,
    lat,
  };
}

export function emptyFilter() {
  return { kinds: new Set(), windows: new Set(), categories: new Set(), minConfidence: 0, query: "" };
}

/** An empty selection in a group means "no restriction" for that group. */
export function matches(facility, filter) {
  if (filter.kinds.size && ![...facility.offerings].some((k) => filter.kinds.has(k))) return false;
  if (filter.windows.size && ![...facility.windows].some((w) => filter.windows.has(w))) return false;
  if (filter.categories.size && !filter.categories.has(facility.category)) return false;
  if (facility.confidence < filter.minConfidence) return false;
  if (filter.query && !facility.search.includes(normalize(filter.query))) return false;
  return true;
}

export function markerKind(offerings) {
  const hire = offerings.has("event_hire");
  const hosting = offerings.has("event_hosting");
  return hire && hosting ? "both" : hire ? "hire" : "hosting";
}

export function countBy(facilities, key) {
  const counts = new Map();
  for (const f of facilities) counts.set(key(f), (counts.get(key(f)) || 0) + 1);
  return counts;
}

function normalize(text) {
  return String(text).toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "");
}
