"""Tests for powermap.facilities (spec: power-facility-dataset)."""

import csv
import json

import pytest
from shapely.geometry import Point, Polygon, shape

from powermap.facilities import PROPERTY_KEYS, Facility, build, main, write_outputs
from tests.test_parsers import CAPACITY_CASES

# Roughly 1 degree of longitude ≈ 101.8 km and 1 degree of latitude ≈ 110.8 km at lat 24.
M_LON = 1 / 101_800
M_LAT = 1 / 110_800


def fac(kind, geom, osm_type="way", osm_id=1, **tags):
    return Facility(osm_type, osm_id, kind, {"power": kind, **tags}, geom)


def square(lon=121.0, lat=24.0, size=0.01):
    return Polygon([(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size)])


# --- 4.1 Facility point geometry, attributes, provenance ----------------------


def test_concave_polygon_point_inside():
    concave = Polygon([(121, 24), (121.02, 24), (121.02, 24.02), (121.019, 24.02), (121.019, 24.001), (121, 24.001)])
    f = fac("plant", concave)
    assert concave.contains(f.point)
    assert f.properties()["geom_src"] == "Polygon"


def test_osm_identifiers():
    props = fac("plant", square(), osm_id=123456).properties()
    assert props["osm_id"] == "w123456"
    assert props["osm_url"] == "https://www.openstreetmap.org/way/123456"


def test_provenance_follows_value():
    props = fac("plant", square(), **{"plant:output:electricity": "550 MW"}).properties()
    assert props["capacity_mw"] == 550 and props["capacity_source"] == "osm"
    assert props["energy"] == "unknown" and props["energy_data_source"] is None
    assert props["energy_sources"] == [] and props["missing_energy"] is True


def test_mixed_energy_properties():
    props = fac("plant", square(), **{"plant:source": "coal;gas"}).properties()
    assert props["energy"] == "mixed" and props["energy_sources"] == ["coal", "gas"]
    assert props["energy_data_source"] == "osm" and props["source_raw"] == "coal;gas"


@pytest.mark.parametrize("tag,expected", CAPACITY_CASES)
def test_capacity_raw_kept_only_when_unparsed(tag, expected):
    tags = {} if tag is None else {"plant:output:electricity": tag}
    props = fac("plant", square(), **tags).properties()
    assert props["capacity_raw"] == (tag if expected is None else None)
    assert props["missing_capacity"] is (expected is None)


def test_empty_raw_tags_become_null():
    props = fac("plant", square(), **{"plant:source": "", "plant:output:electricity": " "}).properties()
    assert props["source_raw"] is None and props["capacity_raw"] is None


def test_name_falls_back_to_name_zh():
    assert fac("plant", square(), **{"name:zh": "大潭發電廠"}).name == "大潭發電廠"
    assert fac("plant", square(), name="  ").name is None


# --- 4.2 Generators inside plants, rooftop exclusion ---------------------------


def test_generators_inside_plant_aggregated():
    plant = fac("plant", square(size=0.05), osm_id=1)
    gens = [fac("generator", Point(121.001 + i * 0.002, 24.01), "node", 100 + i) for i in range(12)]
    result = build([plant, *gens])
    assert [f.ref for f in result.facilities] == ["w1"]
    assert result.facilities[0].n_generators == 12
    assert sum(r["action"] == "generator_in_plant" for r in result.log) == 12


def test_overlapping_plants_assign_to_smallest():
    big = fac("plant", square(size=0.05), osm_id=1)
    small = fac("plant", square(size=0.005), osm_id=2)
    gen = fac("generator", Point(121.001, 24.001), "node", 9)
    build([big, small, gen])
    assert (big.n_generators, small.n_generators) == (0, 1)


ROOFTOP_CASES = [
    ("roof", "solar", "5 MW", False),
    (None, "solar", "0.3 MW", False),
    (None, "solar", "1 MW", True),
    (None, "solar", None, True),
    (None, "wind", "0.5 MW", True),
]


@pytest.mark.parametrize("location,source,output,kept", ROOFTOP_CASES)
def test_rooftop_rule(location, source, output, kept):
    tags = {"generator:source": source}
    if location:
        tags["generator:location"] = location
    if output:
        tags["generator:output:electricity"] = output
    gen = fac("generator", Point(121.5, 24.5), "node", 5, **tags)
    result = build([gen])
    assert (len(result.facilities) == 1) is kept
    assert result.excluded_rooftop_solar == (0 if kept else 1)


# --- 4.3 Same-name merge and dataset output ------------------------------------


def _pair(distance_m):
    area = fac("plant", Point(121.0, 24.0).buffer(0.0001), "way", 2, name="大潭發電廠")
    node = fac("plant", Point(area.point.x + distance_m * M_LON, area.point.y), "node", 1, name="大潭發電廠")
    return [node, area]


def test_same_name_nearby_merged():
    result = build(_pair(120))
    assert [f.ref for f in result.facilities] == ["w2"]
    row = next(r for r in result.log if r["action"] == "same_name_nearby")
    assert (row["kept_osm_id"], row["dropped_osm_id"]) == ("w2", "n1")
    assert row["distance_m"] == pytest.approx(120, abs=2)


def test_same_name_far_apart_kept():
    assert {f.ref for f in build(_pair(800)).facilities} == {"n1", "w2"}


def test_unnamed_not_merged():
    a = fac("plant", Point(121, 24).buffer(0.0001), "way", 2)
    b = fac("plant", Point(121, 24), "node", 1)
    assert len(build([a, b]).facilities) == 2


def test_output_properties_and_nulls(tmp_path):
    result = build([fac("plant", square(), osm_id=3), fac("generator", Point(121.5, 24.5), "node", 4, operator="")])
    out, log = tmp_path / "plants.geojson", tmp_path / "dedup_log.csv"
    write_outputs(result, out, log, None)
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"
    for feature in data["features"]:
        props = feature["properties"]
        assert tuple(props) == PROPERTY_KEYS
        assert feature["geometry"]["type"] == "Point"
        for key in ("name", "operator", "source_raw", "capacity_mw", "capacity_raw", "capacity_source", "energy_data_source"):
            assert props[key] is None, key
        assert props["energy_sources"] == [] and isinstance(props["n_generators"], int)
        assert props["missing_capacity"] is True
        assert list(props)[-4:] == ["missing_energy", "official_id", "energy_primary", "energy_primary_source"]
        assert props["official_id"] is None and props["energy_primary"] is None and props["energy_primary_source"] is None
    with log.open() as fh:
        assert next(csv.reader(fh)) == ["action", "kept_osm_id", "dropped_osm_id", "reason", "distance_m"]


def test_cli(tmp_path, capsys):
    seq = tmp_path / "power.geojsonseq"
    plant = {"type": "Feature", "geometry": square().__geo_interface__,
             "properties": {"osm_type": "way", "osm_id": 1, "tags": {"power": "plant", "plant:source": "solar"}}}
    line = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[121, 24], [121.1, 24]]},
            "properties": {"osm_type": "way", "osm_id": 2, "tags": {"power": "line"}}}
    seq.write_text("\n".join(json.dumps(x) for x in (plant, line)) + "\n")
    args = ["--input", str(seq), "--output", str(tmp_path / "p.geojson"), "--dedup-log", str(tmp_path / "d.csv"),
            "--meta", str(tmp_path / "m.json")]
    assert main(args) == 0
    features = json.loads((tmp_path / "p.geojson").read_text())["features"]
    assert len(features) == 1 and shape(features[0]["geometry"]).within(square())
    assert json.loads((tmp_path / "m.json").read_text())["excluded_rooftop_solar"] == 0
