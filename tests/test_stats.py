"""Tests for powermap.stats (spec: power-data-stats)."""

import json

from powermap.stats import compute_official, compute_stats, main


def plant(energy, sources, missing_capacity=False, official_id=None, capacity_source=None):
    return {"properties": {"energy": energy, "energy_sources": sources, "missing_capacity": missing_capacity,
                           "official_id": official_id, "capacity_source": capacity_source}}


def line(voltage_class):
    return {"properties": {"voltage_class": voltage_class, "missing_voltage": voltage_class == "missing"}}


SUMMARY = {"snapshot": "2026-11-11T21:22:47Z", "excluded_by_region": {"penghu": 57, "kinmen": 7, "matsu": 8, "other": 122}}


def test_all_categories_present_with_zero():
    stats = compute_stats([plant("solar", ["solar"])], [line("hv")], SUMMARY, {})
    assert stats["by_energy"]["geothermal"] == 0
    assert set(stats["by_energy"]) == {"solar", "wind", "hydro", "gas", "coal", "nuclear", "geothermal", "other", "mixed", "unknown"}
    assert set(stats["by_voltage_class"]) == {"ehv", "hv", "mv", "lv", "missing"}
    assert len(stats["by_energy_source"]) == 8


def test_counts_agree_with_datasets():
    plants = [plant("coal", ["coal"], True), plant("unknown", [], True), plant("mixed", ["coal", "gas"])]
    lines = [line("ehv"), line("missing"), line("lv")]
    stats = compute_stats(plants, lines, SUMMARY, {"excluded_rooftop_solar": 7})
    assert stats["facilities"] == 3 == sum(stats["by_energy"].values())
    assert stats["lines"] == 3 == sum(stats["by_voltage_class"].values())
    assert stats["facilities_missing_capacity"] == 2 and stats["lines_missing_voltage"] == 1
    assert stats["excluded_rooftop_solar"] == 7
    assert stats["excluded_outside_main_island"] == {"penghu": 57, "kinmen": 7, "matsu": 8, "other": 122}
    assert stats["snapshot"] == "2026-11-11T21:22:47Z"


def test_mixed_counts_under_each_source():
    stats = compute_stats([plant("mixed", ["coal", "gas"]), plant("gas", ["gas"])], [], SUMMARY, {})
    assert stats["by_energy"]["mixed"] == 1 and stats["by_energy"]["gas"] == 1
    assert stats["by_energy_source"]["coal"] == 1 and stats["by_energy_source"]["gas"] == 2


def test_cli_prints_summary(tmp_path, capsys):
    (tmp_path / "p.geojson").write_text(json.dumps({"features": [plant("wind", ["wind"])]}))
    (tmp_path / "l.geojson").write_text(json.dumps({"features": [line("mv")]}))
    (tmp_path / "s.json").write_text(json.dumps(SUMMARY))
    (tmp_path / "m.json").write_text(json.dumps({"excluded_rooftop_solar": 2}))
    (tmp_path / "o.json").write_text(json.dumps({"source_dir": "raw/2026-11-12", "plants": [{}, {}]}))
    (tmp_path / "d.csv").write_text("action,kept_osm_id,dropped_osm_id,reason,distance_m\n")
    (tmp_path / "x.csv").write_text("official_id,osm_id,osm_capacity_mw,official_capacity_mw,diff_ratio\n")
    (tmp_path / "u.csv").write_text("official_id,name,county,capacity_mw,reason\nipp:A,A,,1,unreviewed\n")
    args = ["--plants", str(tmp_path / "p.geojson"), "--lines", str(tmp_path / "l.geojson"),
            "--summary", str(tmp_path / "s.json"), "--facilities-meta", str(tmp_path / "m.json"),
            "--official", str(tmp_path / "o.json"), "--dedup-log", str(tmp_path / "d.csv"),
            "--diff", str(tmp_path / "x.csv"), "--unmatched", str(tmp_path / "u.csv"),
            "--output", str(tmp_path / "stats.json")]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert out.startswith("=== Statistics ===") and "Facilities:                  1" in out
    stats = json.loads((tmp_path / "stats.json").read_text())
    assert stats["built_at"].endswith("Z") and stats["official"]["unmatched"]["unreviewed"] == 1
    assert "Official plants:             2" in out


def test_official_counts_agree_with_reports():
    plants = [plant("gas", ["gas"], official_id="tp-plant:大潭發電廠", capacity_source="taipower"),
              plant("hydro", ["hydro"], official_id="tp-plant:大甲溪發電廠"),
              plant("hydro", ["hydro"], official_id="tp-plant:大甲溪發電廠"),
              plant("solar", ["solar"])]
    dedup = [{"action": "same_name_nearby"}, {"action": "official_same_plant"}]
    unmatched = [{"reason": "unreviewed"}, {"reason": "unreviewed"}, {"reason": "no_osm"}]
    official = compute_official(plants, {"source_dir": "raw/2026-11-12", "plants": [{}] * 5,
                                         "excluded_outside_main_island": 13},
                                dedup, [{"official_id": "tp-plant:興達發電廠"}], unmatched)
    assert official == {"source_dir": "raw/2026-11-12", "plants": 5, "excluded_outside_main_island": 13,
                        "linked": 2, "facilities_with_official_id": 3, "capacity_filled": 1, "merged": 1,
                        "capacity_discrepancies": 1,
                        "unmatched": {"no_osm": 1, "unreviewed": 2, "osm_missing": 0}}
    assert compute_stats(plants, [], SUMMARY, {}, official=official)["official"]["unmatched"]["unreviewed"] == 2
