# Test fixtures

`recorded/` is a raw-document cache (same layout as `data/cache/`) used by e2e tests with `--offline`.
Files are named by request fingerprint, so a recording only matches the exact request the code sends;
if the Overpass query changes, re-record with `uv run pull-berlin pull` and trim `data/cache/osm/*.json` again.

`recorded/osm/` contains a small extract of OpenStreetMap data.
© OpenStreetMap contributors, available under the Open Database License (ODbL): https://www.openstreetmap.org/copyright
