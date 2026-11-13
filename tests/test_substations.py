"""Tests for powermap.substations (spec: substation-dataset)."""

import json

import pytest
from shapely.geometry import Point, shape

from powermap.substations import PROPERTY_KEYS, build_substations, main


def feature(osm_type, osm_id, geometry, **tags):
    return {"type": "Feature", "geometry": geometry,
            "properties": {"osm_type": osm_type, "osm_id": osm_id, "tags": {"power": "substation", **tags}}}


SQUARE = {"type": "Polygon", "coordinates": [[[121.0, 24.0], [121.01, 24.0], [121.01, 24.01], [121.0, 24.01], [121.0, 24.0]]]}
POINT = {"type": "Point", "coordinates": [121.123456789, 24.987654321]}


def test_polygon_substation_becomes_point():
    out = build_substations([feature("way", 42, SQUARE, name="龍潭變電所", voltage="345000;161000", substation="transmission")])
    assert len(out) == 1
    f = out[0]
    assert f["geometry"]["type"] == "Point"
    assert shape(SQUARE).contains(Point(f["geometry"]["coordinates"]))
    p = f["properties"]
    assert list(p) == list(PROPERTY_KEYS)
    assert p["osm_id"] == "w42"
    assert p["osm_url"] == "https://www.openstreetmap.org/way/42"
    assert p["name"] == "龍潭變電所"
    assert p["substation"] == "transmission"
    assert p["voltage_max_kv"] == 345
    assert p["voltage_class"] == "ehv"
    assert p["voltage_source"] == "osm"
    assert p["missing_voltage"] is False
    assert p["geom_src"] == "Polygon"


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({}, dict(name=None, operator=None, substation=None, voltage_max_kv=None, voltage_class="missing",
                  voltage_source=None, missing_voltage=True)),
        ({"name:zh": "中寮", "voltage": "high"}, dict(name="中寮", operator=None, substation=None, voltage_max_kv=None,
                                                    voltage_class="missing", voltage_source=None, missing_voltage=True)),
        ({"voltage": "69000", "operator": "台灣電力公司"}, dict(name=None, operator="台灣電力公司", substation=None,
                                                            voltage_max_kv=69, voltage_class="mv", voltage_source="osm",
                                                            missing_voltage=False)),
    ],
)
def test_missing_values_stay_null(tags, expected):
    props = build_substations([feature("node", 1, POINT, **tags)])[0]["properties"]
    for key, value in expected.items():
        assert props[key] == value, key


def test_point_kept_and_rounded():
    f = build_substations([feature("node", 7, POINT)])[0]
    assert f["geometry"]["coordinates"] == [121.12346, 24.98765]
    assert f["properties"]["geom_src"] == "Point"


def test_only_substations_sorted_and_not_deduplicated():
    plant = feature("way", 1, SQUARE)
    plant["properties"]["tags"]["power"] = "plant"
    items = [feature("way", 10, SQUARE), feature("relation", 3, SQUARE), feature("way", 2, SQUARE), plant,
             feature("node", 99, POINT)]
    out = build_substations(items)
    assert [f["properties"]["osm_id"] for f in out] == ["n99", "w2", "w10", "r3"]


def test_no_substations_writes_empty_collection(tmp_path):
    src = tmp_path / "power.geojsonseq"
    src.write_text(json.dumps(feature("way", 1, SQUARE) | {"properties": {"osm_type": "way", "osm_id": 1,
                                                                          "tags": {"power": "line"}}}) + "\n")
    out = tmp_path / "substations.geojson"
    assert main(["--input", str(src), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"type": "FeatureCollection", "features": []}
