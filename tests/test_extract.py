"""Tests for powermap.extract (spec: osm-power-extraction)."""

import json

import pytest
from shapely.geometry import LineString, Point

from powermap.extract import ScopeFilter, extract, main
from tests.osm_builder import OsmBuilder, square

MAIN = (121.0, 24.0)  # a point on the Taiwan main island


def _by_id(result):
    return {(f["properties"]["osm_type"], f["properties"]["osm_id"]): f for f in result.features}


# --- Power feature extraction ------------------------------------------------


def test_closed_plant_way_becomes_polygon(tmp_path):
    b = OsmBuilder()
    b.way(square(*MAIN), {"power": "plant", "name": "P"}, way_id=123456, closed=True)
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    feature = _by_id(result)[("way", 123456)]
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["tags"]["name"] == "P"


def test_closed_cable_way_stays_line(tmp_path):
    b = OsmBuilder()
    b.way(square(*MAIN), {"power": "cable"}, way_id=7, closed=True)
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    assert _by_id(result)[("way", 7)]["geometry"]["type"] == "LineString"


def test_substation_is_excluded(tmp_path):
    b = OsmBuilder()
    b.way(square(*MAIN), {"power": "substation"}, way_id=8, closed=True)
    b.node(*MAIN, tags={"power": "tower"}, node_id=900)
    b.node(*MAIN, tags={"power": "generator"}, node_id=901)
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    assert list(_by_id(result)) == [("node", 901)]


def test_multipolygon_relation_plant(tmp_path):
    b = OsmBuilder()
    outer = b.way(square(*MAIN), {}, way_id=20, closed=True)
    b.relation(30, [("w", outer, "outer")], {"type": "multipolygon", "power": "plant"})
    b.relation(31, [("w", outer, "")], {"type": "site", "power": "plant"})
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    assert _by_id(result)[("relation", 30)]["geometry"]["type"] == "Polygon"
    assert result.geometryless_relations == 1


def test_header_timestamp_present(tmp_path):
    b = OsmBuilder()
    b.node(*MAIN, tags={"power": "generator"})
    result = extract(b.write(tmp_path / "a.osm.pbf", timestamp="2026-11-02T21:21:00Z"))
    assert result.snapshot == "2026-11-02T21:21:00Z"
    assert result.warnings == []


def test_header_timestamp_missing(tmp_path):
    b = OsmBuilder()
    b.node(*MAIN, tags={"power": "generator"})
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    assert result.snapshot is None
    assert any("timestamp" in w for w in result.warnings)


# --- Main island scope filter ------------------------------------------------

SCOPE_CASES = [
    (Point(121.0, 24.0), None),  # Taiwan main island
    (Point(121.5, 22.05), None),  # Orchid Island
    (Point(118.35, 24.45), "kinmen"),
    (Point(119.95, 26.15), "matsu"),
    (Point(119.6, 23.57), "penghu"),
    (Point(116.7, 20.7), "other"),  # Pratas
    (Point(119.85, 24.1), None),  # Changhua offshore wind
    (Point(120.0, 25.8), "other"),  # Fujian offshore wind
    (LineString([(119.6, 23.5), (120.15, 23.6)]), None),  # Taiwan–Penghu cable
]


@pytest.mark.parametrize("geom,region", SCOPE_CASES)
def test_scope_decisions(geom, region):
    assert ScopeFilter().region_of(geom) == region


def test_cross_boundary_cable_kept_unclipped(tmp_path):
    b = OsmBuilder()
    b.way([(119.6, 23.5), (120.15, 23.6)], {"power": "cable"}, way_id=5)
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    coords = _by_id(result)[("way", 5)]["geometry"]["coordinates"]
    assert [tuple(c) for c in coords] == [(119.6, 23.5), (120.15, 23.6)]


# --- Extraction summary ------------------------------------------------------


def test_summary_counts_mixed_facilities(tmp_path):
    b = OsmBuilder()
    for i in range(3):
        b.node(121.0 + i * 0.01, 24.0, tags={"power": "plant", "plant:source": "coal;gas"})
    b.node(121.1, 24.0, tags={"power": "plant", "plant:source": "solar"})
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    assert result.mixed_energy_facilities == 3
    assert result.counts == {"plant": {"Point": 4}}


def test_summary_exclusions_by_region(tmp_path):
    b = OsmBuilder()
    for i in range(40):
        b.node(118.3 + i * 0.001, 24.45, tags={"power": "generator"})
    pratas = [b.node(116.7 + i * 0.01, 20.7, tags={"power": "generator"}) for i in range(2)]
    result = extract(b.write(tmp_path / "a.osm.pbf"))
    assert result.excluded_by_region == {"kinmen": 40, "matsu": 0, "penghu": 0, "other": 2}
    assert result.excluded_by_power["generator"] == 42
    assert result.excluded_other_ids == [f"n{i}" for i in pratas]
    assert result.features == []


def test_cli_writes_matching_summary(tmp_path, capsys):
    b = OsmBuilder()
    b.node(*MAIN, tags={"power": "plant", "plant:source": "coal;gas"})
    src = b.write(tmp_path / "a.osm.pbf", timestamp="2026-11-02T21:21:00Z")
    out, summ = tmp_path / "power.geojsonseq", tmp_path / "summary.json"
    assert main(["--input", str(src), "--output", str(out), "--summary", str(summ)]) == 0
    summary = json.loads(summ.read_text())
    printed = capsys.readouterr().out
    assert summary["kept_total"] == 1 and summary["mixed_energy_facilities"] == 1
    assert "plant" in printed and "Multi-source (mixed) facilities: 1" in printed
    assert len(out.read_text().splitlines()) == 1
