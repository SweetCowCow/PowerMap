"""Tests for powermap.lines (spec: power-line-dataset)."""

import json

from powermap.lines import PROPERTY_KEYS, build_lines, main


def way(osm_id, coords, **tags):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"osm_type": "way", "osm_id": osm_id, "tags": {"power": "line", **tags}},
    }


def test_adjacent_ways_stay_separate():
    a = way(1, [[121.0, 24.0], [121.1, 24.0]], voltage="161000")
    b = way(2, [[121.1, 24.0], [121.2, 24.05]], voltage="161000")
    out, _ = build_lines([a, b])
    assert [f["properties"]["osm_id"] for f in out] == ["w1", "w2"]


def test_coordinates_rounded_to_five_decimals():
    wiggly = [[121.0 + i * 0.001234567, 24.0 + (i % 2) * 0.0000013] for i in range(50)]
    out, _ = build_lines([way(3, wiggly)])
    for x, y in out[0]["geometry"]["coordinates"]:
        assert round(x, 5) == x and round(y, 5) == y


def test_simplification_removes_small_wiggles():
    # 1 m sideways wiggles are well below the 10 m tolerance.
    wiggly = [[121.0 + i * 0.001, 24.0 + (i % 2) * 0.00001] for i in range(20)]
    out, _ = build_lines([way(4, wiggly)])
    assert len(out[0]["geometry"]["coordinates"]) == 2


def test_minor_line_without_voltage():
    f = way(5, [[121.0, 24.0], [121.1, 24.0]])
    f["properties"]["tags"]["power"] = "minor_line"
    props = build_lines([f])[0][0]["properties"]
    assert props["kind"] == "minor_line"
    assert props["voltage_max_kv"] is None and props["voltage_raw"] is None
    assert props["voltage_class"] == "missing" and props["voltage_source"] is None
    assert props["missing_voltage"] is True


def test_voltage_source_osm():
    props = build_lines([way(6, [[121.0, 24.0], [121.1, 24.0]], voltage="161000")])[0][0]["properties"]
    assert props["voltage_max_kv"] == 161 and props["voltage_class"] == "hv"
    assert props["voltage_source"] == "osm" and props["missing_voltage"] is False


def test_empty_voltage_tag_is_null():
    props = build_lines([way(11, [[121.0, 24.0], [121.1, 24.0]], voltage="")])[0][0]["properties"]
    assert props["voltage_raw"] is None and props["voltage_class"] == "missing"


def test_submarine_cable_keeps_location():
    f = way(7, [[120.1, 23.6], [119.6, 23.5]], location="underwater", voltage="161000")
    f["properties"]["tags"]["power"] = "cable"
    props = build_lines([f])[0][0]["properties"]
    assert props["kind"] == "cable" and props["location"] == "underwater"


def test_degenerate_line_skipped():
    out, skipped = build_lines([way(8, [[121.0, 24.0], [121.0000001, 24.0]])])
    assert out == [] and skipped == 1


def test_non_line_features_ignored():
    plant = way(9, [[121.0, 24.0], [121.1, 24.0]])
    plant["properties"]["tags"]["power"] = "plant"
    assert build_lines([plant]) == ([], 0)


def test_cli_output_shape(tmp_path):
    seq = tmp_path / "power.geojsonseq"
    seq.write_text(json.dumps(way(10, [[121.0, 24.0], [121.1, 24.0]], voltage="345000;161000")) + "\n")
    out = tmp_path / "lines.geojson"
    assert main(["--input", str(seq), "--output", str(out)]) == 0
    data = json.loads(out.read_text())
    props = data["features"][0]["properties"]
    assert tuple(props) == PROPERTY_KEYS
    assert props["voltage_max_kv"] == 345 and props["voltage_raw"] == "345000;161000"
    assert props["osm_url"] == "https://www.openstreetmap.org/way/10"
