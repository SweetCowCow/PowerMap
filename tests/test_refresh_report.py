"""Tests for powermap.refresh_report (spec: data-refresh, Change report)."""

import json
import shutil
import subprocess
from datetime import date

import pytest

from powermap.refresh_report import build_report, load_base, load_current, main

TODAY = date(2026, 11, 13)


def stats(facilities=1570, no_osm=36, snapshot="2026-11-11T21:22:47Z"):
    return {"snapshot": snapshot, "facilities": facilities, "lines": 2515, "substations": 784,
            "facilities_missing_capacity": 1342, "lines_missing_voltage": 1059,
            "official": {"source_dir": "data/official/raw/2026-11-12", "linked": 50, "located": 30,
                         "unmatched": {"no_osm": no_osm, "unreviewed": 0, "osm_missing": 0}}}


def current(**extra):
    base = {"stats": stats(), "unmatched": [], "diff": [], "enrich_warnings": [], "location_warnings": [],
            "status_warnings": [], "status_rows": []}
    return base | extra


BASE = {"stats": stats(), "unmatched": [], "diff": []}


# --- Change report: example table ----------------------------------------------------------


def test_unreviewed_plant_is_listed_with_hint():
    report, n = build_report(BASE, current(unmatched=[{"official_id": "ipp:新電廠", "name": "新電廠",
                                                        "reason": "unreviewed"}]), TODAY)
    assert "`ipp:新電廠`" in report and "make crosswalk-candidates" in report
    assert n == 1 and report.rstrip().endswith("待處理 1 項")


def test_count_change_row():
    report, _ = build_report(BASE, current(stats=stats(facilities=1575)), TODAY)
    assert "| 設施 | 1,570 → 1,575 (+5) |" in report


def test_status_older_than_365_days():
    row = {"official_id": "tp-plant:核一廠", "checked_at": "2025-11-01"}
    fresh = {"official_id": "tp-plant:核二廠", "checked_at": "2026-01-01"}
    report, n = build_report(BASE, current(status_rows=[row, fresh]), TODAY)
    assert "`tp-plant:核一廠`：查證日期 2025-11-01 已超過一年" in report
    assert "核二廠" not in report and n == 1


def test_nothing_to_review():
    report, n = build_report(BASE, current(), TODAY)
    assert n == 0
    assert "（沒有）" in report and report.rstrip().endswith("待處理 0 項")


# --- Other review items ------------------------------------------------------------------


def test_new_diff_rows_and_missing_base_file():
    diff = [{"official_id": "tp-plant:協和發電廠", "osm_capacity_mw": "2000.0", "official_capacity_mw": "1000.0"},
            {"official_id": "ipp:豐德", "osm_capacity_mw": "980.0", "official_capacity_mw": "2113.8"}]
    # base has no official_diff.csv at all: every row is new
    report, n = build_report({"stats": {}, "unmatched": [], "diff": []}, current(diff=diff), TODAY)
    assert n == 2 and "新的容量差距：`ipp:豐德`" in report
    assert "| 設施 | 0 → 1,570 (+1,570) |" in report
    # same rows already in base: nothing new
    _, n = build_report(BASE | {"diff": diff}, current(diff=diff), TODAY)
    assert n == 0


def test_osm_missing_and_ignored_rows_are_listed():
    report, n = build_report(BASE, current(
        unmatched=[{"official_id": "tp-plant:甲", "name": "甲", "reason": "osm_missing"},
                   {"official_id": "tp-plant:乙", "name": "乙", "reason": "no_osm"}],
        enrich_warnings=["line 9: w1 is not in the facility dataset; ignored"],
        location_warnings=["line 3: tp-re:X is linked to OSM in the crosswalk; row ignored"],
        status_warnings=["line 4: tp-plant:不存在 is not in the official list; row ignored"]), TODAY)
    assert n == 4
    assert "`tp-plant:甲` 甲：對照表的 OSM id 已失效" in report
    assert "乙" not in report  # no_osm is reviewed already
    assert "位置表 `data/official/locations.csv`：line 3" in report
    assert "狀態表 `data/official/status.csv`：line 4" in report


def test_data_sources_section():
    report, _ = build_report(BASE, current(stats=stats(snapshot="2026-12-10T21:00:00Z")), TODAY)
    assert "| OSM 快照 | 2026-11-11T21:22:47Z | 2026-12-10T21:00:00Z |" in report
    assert report.index("## 資料來源") < report.index("## 數量變化") < report.index("## 待處理")


# --- Reading inputs ------------------------------------------------------------------------

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "PATH": "/usr/bin:/bin"})


def write(repo, path, text):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@needs_git
def test_load_base_reads_commit_and_treats_missing_files_as_empty(tmp_path):
    git(tmp_path, "init", "-q")
    write(tmp_path, "data/processed/stats.json", json.dumps(stats(facilities=1500)))
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    write(tmp_path, "data/processed/stats.json", json.dumps(stats(facilities=1600)))  # uncommitted
    base = load_base("HEAD", tmp_path)
    assert base["stats"]["facilities"] == 1500
    assert base["unmatched"] == [] and base["diff"] == []


@needs_git
def test_main_unknown_ref_exits_non_zero(tmp_path, capsys):
    git(tmp_path, "init", "-q")
    code = main(["--base-ref", "no-such-ref", "--output", str(tmp_path / "r.md"), "--root", str(tmp_path)])
    assert code == 1
    assert "no-such-ref" in capsys.readouterr().err
    assert not (tmp_path / "r.md").exists()


def test_load_current_reads_tables(tmp_path):
    write(tmp_path, "data/interim/official_plants.json",
          json.dumps({"plants": [{"official_id": "tp-plant:核一廠"}, {"official_id": "tp-re:A"}]}))
    write(tmp_path, "data/interim/enrich_meta.json", json.dumps({"warnings": ["w"]}))
    write(tmp_path, "data/official/crosswalk.csv", "official_id,osm_ids,relation,note\ntp-re:A,w1,part,\n")
    write(tmp_path, "data/official/locations.csv",
          "official_id,lat,lon,precision,method,source,checked_at,note\n"
          "tp-re:A,24.2,120.6,site,manual,x,2026-11-13,\n")
    write(tmp_path, "data/official/status.csv",
          "official_id,status,since,units,source,checked_at,note\n"
          "tp-plant:核一廠,retired,2019-07,,https://example.org,2025-01-01,\n")
    cur = load_current(tmp_path)
    assert cur["enrich_warnings"] == ["w"]
    assert "linked to OSM" in cur["location_warnings"][0]
    assert [r["official_id"] for r in cur["status_rows"]] == ["tp-plant:核一廠"]
    assert cur["stats"] == {} and cur["unmatched"] == []
