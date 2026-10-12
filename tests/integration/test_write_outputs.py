from __future__ import annotations

import json
from pathlib import Path

from pull_berlin.publishing.renderers import write_outputs
from pull_berlin.publishing.views import FacilityView


def test_writes_csv_json_and_geojson_side_by_side(tmp_path: Path) -> None:
    view = FacilityView(id="osm:node/1", name="X", lat=52.5, lon=13.4, category=None, category_degree=0.0)
    written = write_outputs([view], tmp_path / "out")
    assert sorted(p.name for p in written) == ["facilities.csv", "facilities.geojson", "facilities.json"]
    assert (
        json.loads((tmp_path / "out" / "facilities.geojson").read_text())["features"][0]["properties"]["name"]
        == "X"
    )
