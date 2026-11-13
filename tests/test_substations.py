"""Tests for powermap.substations (spec: substation-dataset)."""

import json

import pytest
from shapely.geometry import Point, shape

from powermap.substations import PROPERTY_KEYS, build_substations, build_substations_with_log, main


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


def test_only_substations_sorted_and_equal_areas_kept():
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
    log = tmp_path / "substation_dedup_log.csv"
    assert main(["--input", str(src), "--output", str(out), "--dedup-log", str(log)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"type": "FeatureCollection", "features": []}
    assert log.read_text(encoding="utf-8").splitlines() == ["action,kept_osm_id,dropped_osm_id,reason,distance_m"]


# --- Contained substation removal ---------------------------------------------------


def square(lon, lat, size):
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size],
                                                [lon, lat + size], [lon, lat]]]}


OUTER = square(121.0, 24.0, 0.01)  # about 1 km
INNER = square(121.004, 24.004, 0.002)  # fully inside OUTER


def ids(features):
    return [f["properties"]["osm_id"] for f in features]


@pytest.mark.parametrize("inner_name, outer_name, inner_geom, dropped, reason", [
    (None, "沙崙一次配電變電所", INNER, "w2", "unnamed"),          # unnamed inside named: inner removed
    ("六家第一次配電變電所", None, INNER, "w1", "unnamed"),          # named inside unnamed: outer removed
    ("義和開閉所", "義和開閉所", INNER, "w2", "same_name"),
    ("台灣電力公司電力修護處南部分處", "同盟變電所", INNER, None, None),
    (None, "變電站", square(121.01, 24.004, 0.002), None, None),   # only touching OUTER
    # 89% inside: shift the 0.002-wide square so 11% of its width sticks out of OUTER
    (None, "某變電所", square(121.01 - 0.002 * 0.89, 24.004, 0.002), None, None),
])
def test_contained_substation_rules(inner_name, outer_name, inner_geom, dropped, reason):
    outer_tags = {} if outer_name is None else {"name": outer_name}
    inner_tags = {} if inner_name is None else {"name": inner_name}
    features, log = build_substations_with_log([feature("way", 1, OUTER, **outer_tags),
                                                feature("way", 2, inner_geom, **inner_tags)])
    assert ids(features) == [i for i in ["w1", "w2"] if i != dropped]
    if dropped:
        kept = "w1" if dropped == "w2" else "w2"
        assert log == [{"action": "substation_contained", "kept_osm_id": kept, "dropped_osm_id": dropped,
                        "reason": reason, "distance_m": log[0]["distance_m"]}]
        assert isinstance(log[0]["distance_m"], float)  # both centred here, so 0.0
    else:
        assert log == []


def test_contained_keeps_smallest_container_and_log_order():
    middle = square(121.002, 24.002, 0.006)
    items = [feature("relation", 5, square(121.0045, 24.0045, 0.001)),  # unnamed, inside middle and OUTER
             feature("way", 9, INNER, name="中層"),                       # named, different: kept
             feature("way", 3, middle, name="中層"),
             feature("way", 1, OUTER, name="外層")]
    features, log = build_substations_with_log(items)
    assert ids(features) == ["w1", "w3"]
    # kept_osm_id is always the other member of the pair, even when it is removed by another pair
    assert [(r["dropped_osm_id"], r["kept_osm_id"], r["reason"]) for r in log] == [
        ("w9", "w3", "same_name"),
        ("r5", "w9", "unnamed"),
    ]


def test_points_are_never_removed_or_containers():
    point_inside = {"type": "Point", "coordinates": [121.005, 24.005]}
    features, log = build_substations_with_log([feature("node", 4, point_inside), feature("way", 1, OUTER)])
    assert ids(features) == ["n4", "w1"]
    assert log == []


def test_main_writes_dedup_log(tmp_path):
    src = tmp_path / "power.geojsonseq"
    src.write_text("\n".join(json.dumps(f) for f in [feature("way", 1, OUTER, name="義和開閉所"),
                                                       feature("way", 2, INNER, name="義和開閉所")]) + "\n")
    out, log = tmp_path / "substations.geojson", tmp_path / "log.csv"
    assert main(["--input", str(src), "--output", str(out), "--dedup-log", str(log)]) == 0
    assert ids(json.loads(out.read_text(encoding="utf-8"))["features"]) == ["w1"]
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "action,kept_osm_id,dropped_osm_id,reason,distance_m"
    assert lines[1].startswith("substation_contained,w1,w2,same_name,")


def test_self_intersecting_area_is_not_removed_and_does_not_fail():
    bowtie = {"type": "Polygon", "coordinates": [[[121.004, 24.004], [121.006, 24.006], [121.006, 24.004],
                                                  [121.004, 24.006], [121.004, 24.004]]]}
    features, log = build_substations_with_log([feature("way", 1, bowtie, name="甲"),
                                                feature("way", 2, square(121.0, 24.0, 0.02), name="乙")])
    assert ids(features) == ["w1", "w2"]  # different names: both kept, and no exception
    assert log == []
