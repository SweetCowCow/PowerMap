"""Tests for powermap.official_points (spec: official-locations)."""

import csv
import json

import pytest

from powermap.official_points import LOCATION_HEADER, LocationError, build, linked_official_ids, load_locations, main

ZHONGKE = "tp-re:中科E/S太陽光電發電站"
PLANTS = [
    {"official_id": ZHONGKE, "name": "中科E/S太陽光電發電站", "county": "台中市", "address": "台中市西屯區科園一路1號",
     "capacity_mw": 0.198, "energy_primary": "solar"},
    {"official_id": "tp-re:恆春風力發電站", "name": "恆春風力發電站", "county": "屏東縣", "address": "屏東縣恆春鎮南灣里",
     "capacity_mw": 4.5, "energy_primary": "wind"},
    {"official_id": "tp-re:觀園風力發電站", "name": "觀園風力發電站", "county": "桃園市", "address": None,
     "capacity_mw": 30.0, "energy_primary": "wind"},
]
OFFICIAL_IDS = {p["official_id"] for p in PLANTS}
ZHONGKE_ROW = [ZHONGKE, "24.20811", "120.61822", "address", "nominatim", "科園一路1號", "2026-11-13", ""]
HENGCHUN_ROW = ["tp-re:恆春風力發電站", "21.97080", "120.76910", "village", "nominatim", "南灣里", "2026-11-13", ""]


def write_csv(path, rows, header=LOCATION_HEADER):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def load(tmp_path, rows, linked=frozenset()):
    return load_locations(write_csv(tmp_path / "locations.csv", rows), OFFICIAL_IDS, set(linked))


# --- Official location table validation: example table -----------------------------


def test_duplicate_official_id_prints_both_rows(tmp_path):
    with pytest.raises(LocationError) as exc:
        load(tmp_path, [ZHONGKE_ROW, ZHONGKE_ROW[:1] + ["24.2", "120.6"] + ZHONGKE_ROW[3:]])
    message = str(exc.value)
    assert "appears on lines [2, 3]" in message
    assert "24.20811" in message and "24.2,120.6" in message


def test_invalid_precision(tmp_path):
    with pytest.raises(LocationError, match=r"line 2: precision 'exact'.*中科E/S"):
        load(tmp_path, [ZHONGKE_ROW[:3] + ["exact"] + ZHONGKE_ROW[4:]])


def test_invalid_method(tmp_path):
    with pytest.raises(LocationError, match="method 'google'"):
        load(tmp_path, [ZHONGKE_ROW[:4] + ["google"] + ZHONGKE_ROW[5:]])


def test_non_numeric_coordinate(tmp_path):
    with pytest.raises(LocationError, match=r"line 2: lat/lon 'abc'.*中科E/S"):
        load(tmp_path, [[ZHONGKE, "abc"] + ZHONGKE_ROW[2:]])


def test_outside_main_island_box(tmp_path):
    with pytest.raises(LocationError, match=r"line 2: .*outside the main island box"):
        load(tmp_path, [[ZHONGKE, "26.15", "119.95"] + ZHONGKE_ROW[3:]])


def test_unknown_official_id_is_ignored_with_warning(tmp_path):
    table = load(tmp_path, [["tp-re:不存在"] + ZHONGKE_ROW[1:], HENGCHUN_ROW])
    assert [r["official_id"] for r in table.rows] == ["tp-re:恆春風力發電站"]
    assert table.warnings == ["line 2: tp-re:不存在 is not in the official list; row ignored"]


def test_linked_official_id_is_ignored_with_warning(tmp_path):
    row = ["tp-re:觀園風力發電站"] + ZHONGKE_ROW[1:]
    table = load(tmp_path, [row], linked={"tp-re:觀園風力發電站"})
    assert table.rows == []
    assert "linked to OSM in the crosswalk" in table.warnings[0]


def test_road_precision_is_valid(tmp_path):
    table = load(tmp_path, [ZHONGKE_ROW[:3] + ["road"] + ZHONGKE_ROW[4:]])
    assert table.rows[0]["precision"] == "road"


def test_missing_column(tmp_path):
    path = write_csv(tmp_path / "locations.csv", [], header=LOCATION_HEADER[:-1])
    with pytest.raises(LocationError, match="missing column"):
        load_locations(path, OFFICIAL_IDS, set())


def test_linked_official_ids_reads_same_and_part(tmp_path):
    path = tmp_path / "crosswalk.csv"
    path.write_text("official_id,osm_ids,relation,note\n"
                    "a,w1,same,\nb,w2;w3,part,\nc,,none,\n", encoding="utf-8")
    assert linked_official_ids(path) == {"a", "b"}
    assert linked_official_ids(tmp_path / "missing.csv") == set()


# --- Official point output -----------------------------------------------------------


def test_located_official_plant_example(tmp_path):
    table = load(tmp_path, [ZHONGKE_ROW])
    collection = build(PLANTS, table)
    (feature,) = collection["features"]
    assert feature["geometry"] == {"type": "Point", "coordinates": [120.61822, 24.20811]}
    props = feature["properties"]
    assert props["capacity_mw"] == 0.198
    assert props["energy_primary"] == "solar"
    assert props["precision"] == "address"


def test_property_order_sorting_and_rounding(tmp_path):
    rows = [HENGCHUN_ROW, [ZHONGKE, "24.2081149", "120.6182249"] + ZHONGKE_ROW[3:]]
    collection = build(PLANTS, load(tmp_path, rows))
    assert [f["properties"]["official_id"] for f in collection["features"]] == sorted([ZHONGKE, HENGCHUN_ROW[0]])
    for feature in collection["features"]:
        assert list(feature["properties"]) == ["official_id", "name", "county", "address", "capacity_mw",
                                               "energy_primary", "precision", "method", "source", "checked_at"]
    zhongke = next(f for f in collection["features"] if f["properties"]["official_id"] == ZHONGKE)
    assert zhongke["geometry"]["coordinates"] == [120.61822, 24.20811]


def write_inputs(tmp_path, location_rows=None):
    official = tmp_path / "official_plants.json"
    official.write_text(json.dumps({"plants": PLANTS}, ensure_ascii=False), encoding="utf-8")
    crosswalk = tmp_path / "crosswalk.csv"
    crosswalk.write_text("official_id,osm_ids,relation,note\n"
                         f"{ZHONGKE},,none,\ntp-re:觀園風力發電站,n1;n2,part,\n", encoding="utf-8")
    unmatched = tmp_path / "unmatched.csv"
    unmatched.write_text(f"official_id,name,county,capacity_mw,reason\n{ZHONGKE},中科E/S太陽光電發電站,台中市,0.198,no_osm\n",
                         encoding="utf-8")
    locations = tmp_path / "locations.csv"
    if location_rows is not None:
        write_csv(locations, location_rows)
    return official, crosswalk, locations, unmatched


def run_main(tmp_path, location_rows=None):
    official, crosswalk, locations, _ = write_inputs(tmp_path, location_rows)
    output = tmp_path / "out" / "official_points.geojson"
    code = main(["--official", str(official), "--crosswalk", str(crosswalk), "--locations", str(locations),
                 "--output", str(output)])
    return code, output


def test_main_missing_table_writes_empty_collection(tmp_path):
    code, output = run_main(tmp_path)
    assert code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {"type": "FeatureCollection", "features": []}


def test_main_end_to_end_keeps_unmatched(tmp_path, capsys):
    unmatched = tmp_path / "unmatched.csv"
    code, output = run_main(tmp_path, [ZHONGKE_ROW, ["tp-re:觀園風力發電站"] + ZHONGKE_ROW[1:]])
    assert code == 0
    features = json.loads(output.read_text(encoding="utf-8"))["features"]
    assert [f["properties"]["official_id"] for f in features] == [ZHONGKE]
    assert "linked to OSM" in capsys.readouterr().err
    # the location table never touches unmatched.csv: the plant is still "no_osm"
    assert f"{ZHONGKE},中科E/S太陽光電發電站,台中市,0.198,no_osm" in unmatched.read_text(encoding="utf-8")


def test_main_invalid_table_exits_non_zero(tmp_path, capsys):
    code, output = run_main(tmp_path, [[ZHONGKE, "26.15", "119.95"] + ZHONGKE_ROW[3:]])
    assert code == 1
    assert not output.exists()
    assert "line 2" in capsys.readouterr().err
