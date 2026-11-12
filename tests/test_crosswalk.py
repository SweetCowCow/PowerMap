"""Tests for powermap.crosswalk (spec: official-crosswalk)."""

import csv

import pytest

from powermap.crosswalk import CrosswalkError, find_candidates, load_crosswalk, main, normalize_name


# --- Name normalization ---------------------------------------------------------------


@pytest.mark.parametrize("name,expected", [
    ("台電大潭發電廠", "大潭"),
    ("臺中發電廠", "台中"),
    ("核三廠", "核三"),
    ("石門風力發電站/Shimen Wind Power Station", "石門風力"),
    ("協和電廠－珠山分廠", "協和電廠-珠山"),  # NFKC turns the full-width dash half-width
    ("大潭", "大潭"),
    ("中科E/S太陽光電發電站/Zhongke E/S Solar Power Station", "中科E/S太陽光電"),
])
def test_normalize_name(name, expected):
    assert normalize_name(name) == expected


def test_normalize_handles_width_space_and_ascii_names():
    assert normalize_name("大潭　發電廠") == "大潭"
    assert normalize_name("ＡＢＣ電廠") == "ABC"
    assert normalize_name("E/S Solar") == "E/SSolar"  # pure-English names are not cut
    assert normalize_name(None) == "" and normalize_name("廠") == "廠"


# --- Crosswalk candidates ---------------------------------------------------------------


def official(official_id, name, normalized, county="高雄市", capacity=100.0):
    return {"official_id": official_id, "name": name, "name_normalized": normalized, "county": county,
            "capacity_mw": capacity}


def facility(osm_id, name, capacity=None, kind="plant"):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [120.2, 22.9]},
            "properties": {"osm_id": osm_id, "name": name, "kind": kind, "capacity_mw": capacity,
                           "osm_url": f"https://www.openstreetmap.org/way/{osm_id[1:]}"}}


def test_exact_and_contains_candidates():
    plants = [official("tp-plant:興達發電廠", "興達發電廠", "興達")]
    facs = [facility("w307905912", "3900MW興達複循環燃煤電廠"), facility("w1", "興達發電廠", 4326),
            facility("w2", "大林發電廠"), facility("w3", None)]
    rows = find_candidates(plants, facs)
    assert [(r["osm_id"], r["match_type"]) for r in rows] == [("w1", "exact"), ("w307905912", "contains")]
    assert rows[0]["osm_capacity_mw"] == 4326 and rows[1]["osm_capacity_mw"] == ""


def test_plant_without_candidates_listed():
    rows = find_candidates([official("tp-plant:核三廠", "核三廠", "核三", "屏東縣")], [facility("w1", "大潭發電廠")])
    assert len(rows) == 1
    assert rows[0]["official_id"] == "tp-plant:核三廠" and rows[0]["match_type"] == "none"
    assert rows[0]["osm_id"] == "" and rows[0]["osm_url"] == ""


def test_single_character_does_not_match():
    rows = find_candidates([official("ipp:X", "X", "台")], [facility("w1", "台中發電廠")])
    assert rows[0]["match_type"] == "none"


def test_cli_writes_candidates(tmp_path, capsys):
    import json
    (tmp_path / "o.json").write_text(json.dumps({"plants": [official("tp-plant:興達發電廠", "興達發電廠", "興達")]}))
    (tmp_path / "f.geojson").write_text(json.dumps({"features": [facility("w1", "興達發電廠")]}))
    out = tmp_path / "c.csv"
    assert main(["--official", str(tmp_path / "o.json"), "--facilities", str(tmp_path / "f.geojson"),
                 "--output", str(out)]) == 0
    with out.open() as fh:
        assert next(csv.reader(fh))[-1] == "match_type"
    assert "exact 1, contains 0, none 0" in capsys.readouterr().out


# --- Crosswalk file validation ---------------------------------------------------------------

OFFICIAL_IDS = {"tp-plant:大潭發電廠", "tp-plant:通霄發電廠", "tp-plant:核三廠"}
FACILITY_IDS = {"w1", "w2", "r18726493", "w661662183"}


def write_crosswalk(path, rows, header="official_id,osm_ids,relation,note"):
    path.write_text("\n".join([header] + rows) + "\n", encoding="utf-8")
    return path


def test_valid_crosswalk(tmp_path):
    path = write_crosswalk(tmp_path / "c.csv", ["tp-plant:大潭發電廠,r18726493;w661662183,same,兩個範圍",
                                                 "tp-plant:核三廠,,none,"])
    cw = load_crosswalk(path, OFFICIAL_IDS, FACILITY_IDS)
    assert cw.links["tp-plant:大潭發電廠"].osm_ids == ["r18726493", "w661662183"]
    assert cw.links["tp-plant:核三廠"].relation == "none" and cw.warnings == []


def test_osm_id_used_twice_rejected(tmp_path):
    path = write_crosswalk(tmp_path / "c.csv", ["tp-plant:大潭發電廠,w661662183,same,",
                                                 "tp-plant:通霄發電廠,w1;w661662183,same,"])
    with pytest.raises(CrosswalkError, match=r"w661662183 appears on lines \[2, 3\]") as exc:
        load_crosswalk(path, OFFICIAL_IDS, FACILITY_IDS)
    assert "line 2: tp-plant:大潭發電廠,w661662183,same," in str(exc.value)
    assert "line 3: tp-plant:通霄發電廠,w1;w661662183,same," in str(exc.value)


def test_official_id_twice_and_bad_relation_rejected(tmp_path):
    path = write_crosswalk(tmp_path / "c.csv", ["tp-plant:大潭發電廠,w1,same,", "tp-plant:大潭發電廠,w2,dup,"])
    with pytest.raises(CrosswalkError) as exc:
        load_crosswalk(path, OFFICIAL_IDS, FACILITY_IDS)
    assert "relation 'dup'" in str(exc.value) and "official_id tp-plant:大潭發電廠" in str(exc.value)


def test_stale_osm_id_ignored_with_warning(tmp_path):
    path = write_crosswalk(tmp_path / "c.csv", ["tp-plant:大潭發電廠,w1;w999,same,"])
    cw = load_crosswalk(path, OFFICIAL_IDS, FACILITY_IDS)
    assert cw.links["tp-plant:大潭發電廠"].osm_ids == ["w1"]
    assert cw.ignored_ids == 1 and any("w999" in w for w in cw.warnings)


def test_all_ids_stale_reported_osm_missing(tmp_path):
    path = write_crosswalk(tmp_path / "c.csv", ["tp-plant:大潭發電廠,w998;w999,part,"])
    cw = load_crosswalk(path, OFFICIAL_IDS, FACILITY_IDS)
    assert cw.osm_missing == ["tp-plant:大潭發電廠"] and "tp-plant:大潭發電廠" not in cw.links


def test_unknown_official_id_ignored(tmp_path):
    path = write_crosswalk(tmp_path / "c.csv", ["tp-plant:協和發電廠,w1,same,"])
    cw = load_crosswalk(path, OFFICIAL_IDS, FACILITY_IDS)
    assert cw.links == {} and any("協和" in w for w in cw.warnings)


def test_missing_file_means_unreviewed(tmp_path):
    cw = load_crosswalk(tmp_path / "absent.csv", OFFICIAL_IDS, FACILITY_IDS)
    assert cw.links == {} and cw.warnings


def test_missing_column_rejected(tmp_path):
    path = write_crosswalk(tmp_path / "c.csv", ["tp-plant:大潭發電廠,w1"], header="official_id,osm_ids")
    with pytest.raises(CrosswalkError, match="relation"):
        load_crosswalk(path, OFFICIAL_IDS, FACILITY_IDS)
