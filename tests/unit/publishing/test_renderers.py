from __future__ import annotations

import csv
import io
import json

from pull_berlin.publishing.renderers import render_csv, render_geojson, render_json
from pull_berlin.publishing.views import ClaimView, EvidenceView, FacilityView, OfferingView

VIEW = FacilityView(
    id="osm:node/1",
    name="Tresor",
    lat=52.5106,
    lon=13.4199,
    category="club",
    category_degree=0.8,
    offerings=(OfferingView(kind="event_hosting", windows=("evening", "night"), confidence=0.8),),
    refs=("osm:node/1",),
    websites=("https://tresorberlin.com",),
    claims=(
        ClaimView(
            proposition="hosts_evening_events",
            confidence=0.8,
            evidence=(
                EvidenceView(
                    "osm", "https://www.openstreetmap.org/node/1", "amenity=nightclub", "supports", 1.0
                ),
            ),
        ),
    ),
)


def test_csv_has_one_row_per_facility_with_flat_columns() -> None:
    (row,) = csv.DictReader(io.StringIO(render_csv([VIEW])))
    assert row["name"] == "Tresor"
    assert row["offerings"] == "event_hosting"
    assert (row["evening"], row["night"]) == ("true", "true")
    assert row["category"] == "club"


def test_csv_of_no_facilities_still_has_a_header() -> None:
    assert render_csv([]).splitlines()[0].startswith("id,name,lat,lon")


def test_geojson_is_a_feature_collection_with_lon_lat_points() -> None:
    collection = json.loads(render_geojson([VIEW]))
    (feature,) = collection["features"]
    assert collection["type"] == "FeatureCollection"
    assert feature["geometry"] == {"type": "Point", "coordinates": [13.4199, 52.5106]}


def test_geojson_properties_are_flat_for_map_styling() -> None:
    properties = json.loads(render_geojson([VIEW]))["features"][0]["properties"]
    assert properties["offerings"] == "event_hosting"
    assert properties["night"] is True
    assert properties["max_confidence"] == 0.8


def test_json_keeps_full_provenance() -> None:
    (facility,) = json.loads(render_json([VIEW]))["facilities"]
    assert facility["claims"][0]["evidence"][0]["excerpt"] == "amenity=nightclub"


def test_json_states_its_licence_attribution() -> None:
    assert "OpenStreetMap" in json.loads(render_json([VIEW]))["attribution"]
