"""Tests for powermap.enrich (spec: official-crosswalk, power-facility-dataset)."""

import csv
import json

import pytest

from powermap.crosswalk import Crosswalk, Link
from powermap.enrich import enrich, main
from powermap.facilities import PROPERTY_KEYS


def facility(osm_id, capacity=None, n_generators=0, lon=121.0, energy="gas", sources=("gas",)):
    props = {k: None for k in PROPERTY_KEYS}
    props.update(osm_id=osm_id, osm_url=f"https://www.openstreetmap.org/way/{osm_id[1:]}", kind="plant",
                 energy=energy, energy_sources=list(sources), energy_data_source="osm", capacity_mw=capacity,
                 capacity_source=None if capacity is None else "osm", n_generators=n_generators,
                 geom_src="Polygon", missing_capacity=capacity is None, missing_energy=False)
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, 25.0]}, "properties": props}


def plant(official_id, capacity, primary="gas", name=None, county="桃園市"):
    return {"official_id": official_id, "name": name or official_id.split(":")[1], "county": county,
            "capacity_mw": capacity, "energy_primary": primary}


def crosswalk(*links, osm_missing=()):
    return Crosswalk(links={l.official_id: l for l in links}, osm_missing=list(osm_missing))


def props_of(result):
    return {f["properties"]["osm_id"]: f["properties"] for f in result.features}


DATAN = "tp-plant:大潭發電廠"
HSINTA = "tp-plant:興達發電廠"


def test_duplicate_areas_merged_and_filled():
    feats = [facility("r18726493", n_generators=2, lon=121.0), facility("w661662183", n_generators=1, lon=121.001)]
    result = enrich(feats, [plant(DATAN, 4984.2)], crosswalk(Link(DATAN, "same", ["r18726493", "w661662183"])))
    props = props_of(result)
    assert list(props) == ["r18726493"]
    kept = props["r18726493"]
    assert kept["capacity_mw"] == 4984.2 and kept["capacity_source"] == "taipower" and kept["missing_capacity"] is False
    assert kept["n_generators"] == 3 and kept["official_id"] == DATAN
    assert kept["energy_primary"] == "gas" and kept["energy_primary_source"] == "taipower"
    row = result.log[0]
    assert (row["action"], row["kept_osm_id"], row["dropped_osm_id"], row["reason"]) == \
        ("official_same_plant", "r18726493", "w661662183", DATAN)
    assert 95 < row["distance_m"] < 110  # 0.001° of longitude at lat 25 ≈ 101 m


def test_osm_capacity_not_overwritten():
    feats = [facility("w1", capacity=4326, energy="mixed", sources=("coal", "gas"))]
    result = enrich(feats, [plant(HSINTA, 3325.95)], crosswalk(Link(HSINTA, "same", ["w1"])))
    props = props_of(result)["w1"]
    assert props["capacity_mw"] == 4326 and props["capacity_source"] == "osm"
    assert props["energy_primary"] == "gas" and props["energy_primary_source"] == "taipower"
    assert props["energy"] == "mixed" and props["energy_sources"] == ["coal", "gas"]


def test_part_relation_keeps_facilities_apart():
    tachia = "tp-plant:大甲溪發電廠"
    feats = [facility("w1", lon=121.0), facility("w2", lon=121.1)]
    result = enrich(feats, [plant(tachia, 1150.275, "hydro")], crosswalk(Link(tachia, "part", ["w1", "w2"])))
    props = props_of(result)
    assert list(props) == ["w1", "w2"] and result.log == []
    for p in props.values():
        assert p["official_id"] == tachia and p["capacity_mw"] is None and p["energy_primary"] == "hydro"


def test_unlinked_facility_keeps_nulls():
    result = enrich([facility("w5")], [plant(DATAN, 4984.2)], crosswalk())
    props = props_of(result)["w5"]
    assert props["official_id"] is None and props["energy_primary"] is None and props["energy_primary_source"] is None


# --- Discrepancy and unmatched reports ----------------------------------------------------


def test_large_difference_reported():
    result = enrich([facility("w1", capacity=4326)], [plant(HSINTA, 3325.95)],
                    crosswalk(Link(HSINTA, "same", ["w1"])))
    assert result.diff == [{"official_id": HSINTA, "osm_id": "w1", "osm_capacity_mw": 4326,
                            "official_capacity_mw": 3325.95, "diff_ratio": 0.301}]


@pytest.mark.parametrize("osm,threshold,reported", [(120, 0.2, False), (121, 0.2, True), (110, 0.05, True)])
def test_difference_threshold(osm, threshold, reported):
    result = enrich([facility("w1", capacity=osm)], [plant("ipp:X", 100)],
                    crosswalk(Link("ipp:X", "same", ["w1"])), threshold)
    assert bool(result.diff) is reported


def test_unmatched_reasons():
    plants = [plant("ipp:海湖", 900), plant("tp-plant:龍門廠", 2700, "nuclear"), plant(DATAN, 4984.2),
              plant("tp-plant:核三廠", 1902, "nuclear")]
    cw = crosswalk(Link("tp-plant:龍門廠", "none", []), Link(DATAN, "same", ["w1"]), osm_missing=["tp-plant:核三廠"])
    result = enrich([facility("w1")], plants, cw)
    assert [(r["official_id"], r["reason"]) for r in result.unmatched] == [
        ("ipp:海湖", "unreviewed"), ("tp-plant:龍門廠", "no_osm"), ("tp-plant:核三廠", "osm_missing")]


# --- CLI ------------------------------------------------------------------------------------


def test_cli_writes_all_outputs(tmp_path, capsys):
    (tmp_path / "f.geojson").write_text(json.dumps({"features": [facility("r1"), facility("w2", lon=121.001)]}))
    (tmp_path / "osm_log.csv").write_text("action,kept_osm_id,dropped_osm_id,reason,distance_m\n"
                                          "same_name_nearby,w2,n9,same name 'X',12.0\n", encoding="utf-8")
    (tmp_path / "o.json").write_text(json.dumps({"plants": [plant(DATAN, 4984.2), plant("ipp:海湖", 900)]},
                                                ensure_ascii=False), encoding="utf-8")
    (tmp_path / "cw.csv").write_text(f"official_id,osm_ids,relation,note\n{DATAN},r1;w2,same,\n", encoding="utf-8")
    out = {k: tmp_path / v for k, v in dict(output="p.geojson", dedup="d.csv", unmatched="u.csv", diff="x.csv",
                                            meta="m.json").items()}
    args = ["--facilities", str(tmp_path / "f.geojson"), "--dedup-log-osm", str(tmp_path / "osm_log.csv"),
            "--official", str(tmp_path / "o.json"), "--crosswalk", str(tmp_path / "cw.csv"),
            "--output", str(out["output"]), "--dedup-log", str(out["dedup"]), "--unmatched", str(out["unmatched"]),
            "--diff", str(out["diff"]), "--meta", str(out["meta"])]
    assert main(args) == 0
    with out["dedup"].open() as fh:
        assert [r["action"] for r in csv.DictReader(fh)] == ["same_name_nearby", "official_same_plant"]
    with out["unmatched"].open() as fh:
        assert [r["reason"] for r in csv.DictReader(fh)] == ["unreviewed"]
    assert json.loads(out["meta"].read_text())["unreviewed"] == 1
    assert "Unreviewed official plants: 1; ignored crosswalk ids: 0" in capsys.readouterr().out
    features = json.loads(out["output"].read_text())["features"]
    assert [f["properties"]["osm_id"] for f in features] == ["r1"]
    assert tuple(features[0]["properties"]) == PROPERTY_KEYS


def test_cli_invalid_crosswalk_exits_nonzero(tmp_path, capsys):
    (tmp_path / "f.geojson").write_text(json.dumps({"features": [facility("w1")]}))
    (tmp_path / "o.json").write_text(json.dumps({"plants": [plant(DATAN, 1), plant("ipp:X", 1)]}))
    (tmp_path / "cw.csv").write_text(f"official_id,osm_ids,relation,note\n{DATAN},w1,same,\nipp:X,w1,same,\n")
    args = ["--facilities", str(tmp_path / "f.geojson"), "--dedup-log-osm", "x", "--official", str(tmp_path / "o.json"),
            "--crosswalk", str(tmp_path / "cw.csv")] + [a for k in ("output", "dedup-log", "unmatched", "diff", "meta")
                                                       for a in (f"--{k}", str(tmp_path / k))]
    assert main(args) == 1
    assert "w1 appears on lines [2, 3]" in capsys.readouterr().err
