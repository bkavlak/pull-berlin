"""Whole pipeline, offline, against a recorded Overpass response (tests/fixtures/recorded)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pull_berlin.cli import main

RECORDED = Path(__file__).resolve().parents[1] / "fixtures" / "recorded"


def test_offline_pull_from_recording_produces_consistent_exports(tmp_path: Path) -> None:
    out = tmp_path / "out"
    exit_code = main(["pull", "--offline", "--cache", str(RECORDED), "--out", str(out)])

    assert exit_code == 0
    rows = list(csv.DictReader((out / "facilities.csv").open()))
    features = json.loads((out / "facilities.geojson").read_text())["features"]
    facilities = json.loads((out / "facilities.json").read_text())["facilities"]
    assert len(rows) == len(features) == len(facilities) > 0
    assert all(row["offerings"] for row in rows)
    assert all(52.33 < f["geometry"]["coordinates"][1] < 52.68 for f in features)
