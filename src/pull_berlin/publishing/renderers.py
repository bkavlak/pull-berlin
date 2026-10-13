"""Exports of the catalog: CSV (spreadsheets), GeoJSON (maps), JSON (full provenance)."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from pull_berlin.publishing.views import FacilityView

OSM_ATTRIBUTION = (
    "Contains information from OpenStreetMap, © OpenStreetMap contributors, available under the ODbL."
)

_CSV_COLUMNS = (
    "id",
    "name",
    "lat",
    "lon",
    "category",
    "category_degree",
    "offerings",
    "evening",
    "night",
    "max_confidence",
    "websites",
    "refs",
    "reviewed_by",
)


def render_csv(views: Sequence[FacilityView]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for view in views:
        writer.writerow({**_flat(view), "evening": _bool(view.evening), "night": _bool(view.night)})
    return buffer.getvalue()


def render_geojson(views: Sequence[FacilityView]) -> str:
    features = [
        {
            "type": "Feature",
            "id": view.id,
            "geometry": {"type": "Point", "coordinates": [view.lon, view.lat]},
            "properties": {key: value for key, value in _flat(view).items() if key not in ("lat", "lon")},
        }
        for view in views
    ]
    return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=1)


def render_json(views: Sequence[FacilityView], attribution: str = OSM_ATTRIBUTION) -> str:
    facilities = [
        {**asdict(view), "evening": view.evening, "night": view.night, "max_confidence": view.max_confidence}
        for view in views
    ]
    return json.dumps({"attribution": attribution, "facilities": facilities}, ensure_ascii=False, indent=1)


def write_outputs(views: Sequence[FacilityView], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "facilities.csv": render_csv(views),
        "facilities.geojson": render_geojson(views),
        "facilities.json": render_json(views),
    }
    written = []
    for name, content in files.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def _flat(view: FacilityView) -> dict[str, object]:
    return {
        "id": view.id,
        "name": view.name,
        "lat": view.lat,
        "lon": view.lon,
        "category": view.category or "",
        "category_degree": view.category_degree,
        "offerings": ";".join(o.kind for o in view.offerings),
        "evening": view.evening,
        "night": view.night,
        "max_confidence": view.max_confidence,
        "websites": ";".join(view.websites),
        "refs": ";".join(view.refs),
        "reviewed_by": ";".join(view.reviewers),
    }


def _bool(value: bool) -> str:
    return "true" if value else "false"
