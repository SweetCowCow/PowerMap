"""Tests for powermap.official (spec: official-power-data)."""

import json
from datetime import datetime, timezone

import pytest

from powermap.official import (
    Dataset,
    OfficialDataError,
    download,
    latest_snapshot,
    main,
    map_fuel,
    normalize,
)

NOW = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)

TH_HEADER = "電廠名稱,郵遞區號,地址-縣市鄉鎮,地址-村里,地址-街路門牌,連絡電話,傳真電話,機組名稱,商轉日期,裝置容量(瓩),燃料種類"
NU_HEADER = '電廠名稱,地址,連絡電話,傳真電話,機組名稱,商轉日期,"裝置容量MWe"'
RE_HEADER = ("發電站編號/Number of The Power Station,能源別/Type of Energy,發電站名稱/Name of The Power Station,"
             "場址編號/Number of the Site,場址說明/Description fo The Site,型號/Model,"
             "裝置容量(瓩)/Installed Capacity(kW),風機數量/Number of The Windturbine,地址/Address,"
             "申設狀態/Application Status,備註/Remarks")


def th_row(plant, county, unit, kw, fuel):
    return f"{plant},33845,{county},,地址1號,,,{unit},20090101,{kw},{fuel}"


def write_snapshot(root, thermal=None, nuclear=None, renewable=None, units=None):
    root.mkdir(parents=True, exist_ok=True)
    (root / "thermal_hydro.csv").write_text("﻿" + "\n".join([TH_HEADER] + (thermal or [])) + "\n", encoding="utf-8")
    (root / "nuclear.csv").write_text("\n".join([NU_HEADER] + (nuclear or [])) + "\n", encoding="utf-8")
    (root / "renewable.csv").write_text("\n".join([RE_HEADER] + (renewable or [])) + "\n", encoding="utf-8")
    (root / "units.json").write_text("﻿" + json.dumps({"DateTime": "2026-11-12T15:20:00", "aaData": units or []},
                                                             ensure_ascii=False), encoding="utf-8")
    return root


def unit(kind, name, mw):
    return {"機組類型": kind, "機組名稱": name, "裝置容量(MW)": mw, "淨發電量(MW)": "0"}


def by_id(result):
    return {p["official_id"]: p for p in result["plants"]}


# --- Official snapshot download ----------------------------------------------------


def _sources(tmp_path, names=("a.csv", "b.csv", "c.csv", "d.json")):
    datasets = []
    for i, name in enumerate(names):
        src = tmp_path / "src" / name
        src.parent.mkdir(exist_ok=True)
        src.write_text(f"content {i}", encoding="utf-8")
        datasets.append(Dataset(str(i), f"title {i}", src.as_uri(), name))
    return tuple(datasets)


def test_download_creates_dated_snapshot(tmp_path):
    target = download(tmp_path / "raw", _sources(tmp_path), now=NOW)
    assert target == tmp_path / "raw" / "2026-11-12"
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["downloaded_at"] == "2026-11-12T08:00:00Z"
    assert manifest["license"] == "政府資料開放授權條款第1版"
    assert [f["file"] for f in manifest["files"]] == ["a.csv", "b.csv", "c.csv", "d.json"]
    assert all(len(f["sha256"]) == 64 for f in manifest["files"])
    assert (target / "a.csv").read_text(encoding="utf-8") == "content 0"


def test_failed_download_leaves_no_snapshot(tmp_path):
    datasets = _sources(tmp_path)
    broken = datasets[:3] + (Dataset("x", "missing", (tmp_path / "nope.json").as_uri(), "d.json"),)
    with pytest.raises(OSError):
        download(tmp_path / "raw", broken, now=NOW)
    assert list((tmp_path / "raw").iterdir()) == []


def test_existing_snapshot_not_overwritten(tmp_path):
    (tmp_path / "raw" / "2026-11-12").mkdir(parents=True)
    with pytest.raises(FileExistsError, match="2026-11-12"):
        download(tmp_path / "raw", _sources(tmp_path), now=NOW)


def test_existing_snapshot_reused_on_request(tmp_path):
    target = tmp_path / "raw" / "2026-11-12"
    target.mkdir(parents=True)
    (target / "a.csv").write_text("old", encoding="utf-8")
    broken = (Dataset("x", "missing", (tmp_path / "nope.json").as_uri(), "a.csv"),)  # would fail if fetched
    assert download(tmp_path / "raw", broken, now=NOW, reuse_existing=True) == target
    assert (target / "a.csv").read_text(encoding="utf-8") == "old"
    assert sorted(p.name for p in (tmp_path / "raw").iterdir()) == ["2026-11-12"]


def test_cli_reuse_existing(tmp_path, capsys):
    today = tmp_path / "raw" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today.mkdir(parents=True)
    assert main(["download", "--dest", str(tmp_path / "raw"), "--reuse-existing"]) == 0
    assert "Reusing existing snapshot" in capsys.readouterr().out
    assert list(today.iterdir()) == []


def test_cli_existing_without_flag_fails(tmp_path, capsys):
    (tmp_path / "raw" / datetime.now(timezone.utc).strftime("%Y-%m-%d")).mkdir(parents=True)
    assert main(["download", "--dest", str(tmp_path / "raw")]) == 1
    assert "already exists" in capsys.readouterr().err


def test_latest_snapshot_picks_newest_date(tmp_path):
    for name in ("2026-11-01", "2026-11-12", ".download-x", "notes"):
        (tmp_path / name).mkdir()
    assert latest_snapshot(tmp_path).name == "2026-11-12"


# --- Official plant normalization ----------------------------------------------------


def test_units_are_summed_into_plant(tmp_path):
    rows = [th_row("大潭發電廠", "桃園市觀音區", f"CC#{i}", kw, "天然氣")
            for i, kw in enumerate([742700, 742700, 724700, 742700, 742700, 742700, 546000], 1)]
    plant = by_id(normalize(write_snapshot(tmp_path, thermal=rows)))["tp-plant:大潭發電廠"]
    assert plant["capacity_mw"] == pytest.approx(4984.2)
    assert plant["n_units"] == 7 and plant["county"] == "桃園市" and plant["name_normalized"] == "大潭"
    assert plant["energy_primary"] == "gas" and plant["dataset_id"] == "8934"


def test_private_plants_from_realtime_list(tmp_path):
    units = [unit("民營電廠-燃氣", "海湖#1", "450.0"), unit("民營電廠-燃氣", "海湖#2", "450.0"),
             unit("民營電廠-燃氣", "小計", "6389.7(10.408%)"), unit("燃氣", "大潭CC#1", "742.7")]
    result = normalize(write_snapshot(tmp_path, units=units))
    assert list(by_id(result)) == ["ipp:海湖"]
    plant = by_id(result)["ipp:海湖"]
    assert plant["capacity_mw"] == 900.0 and plant["county"] is None and plant["energy_primary"] == "gas"


def test_renewable_sites_grouped_by_station(tmp_path):
    rows = ["8,太陽能/Solar,彰化彰濱太陽光電發電站/Changhua Changbin Solar Power Station,17,彰化彰濱,M,99999,,彰化縣鹿港鎮崙工路53號,取得電業執照,",
            "-,太陽能/Solar,彰化彰濱太陽光電發電站/Changhua Changbin Solar Power Station,18,彰化彰濱2期,M,16511,,彰化縣鹿港鎮崙尾段1地號,取得設備登記,",
            ",,,,,,,,,,"]
    plant = by_id(normalize(write_snapshot(tmp_path, renewable=rows)))["tp-re:彰化彰濱太陽光電發電站"]
    assert plant["capacity_mw"] == pytest.approx(116.51) and plant["n_units"] == 2
    assert plant["energy_primary"] == "solar" and plant["county"] == "彰化縣"


def test_station_name_with_slash_kept_whole(tmp_path):
    rows = ["7,太陽能/Solar,中科E/S太陽光電發電站/Zhongke E/S Solar Power Station,16,中科E/S,M,198,,台中市西屯區科園一路1號,取得電業執照,"]
    result = normalize(write_snapshot(tmp_path, renewable=rows))
    assert list(by_id(result)) == ["tp-re:中科E/S太陽光電發電站"]
    assert by_id(result)["tp-re:中科E/S太陽光電發電站"]["name_normalized"] == "中科E/S太陽光電"


def test_nuclear_capacity_in_mw(tmp_path):
    rows = ["核三廠,屏東縣恆春鎮南灣里1號,,,一號機,19840727,951", "核三廠,屏東縣恆春鎮南灣里1號,,,二號機,19850518,951"]
    plant = by_id(normalize(write_snapshot(tmp_path, nuclear=rows)))["tp-plant:核三廠"]
    assert plant["capacity_mw"] == 1902 and plant["energy_primary"] == "nuclear" and plant["dataset_id"] == "10858"


def test_missing_column_fails_loudly(tmp_path):
    write_snapshot(tmp_path)
    (tmp_path / "thermal_hydro.csv").write_text(TH_HEADER.replace(",裝置容量(瓩)", "") + "\n", encoding="utf-8")
    with pytest.raises(OfficialDataError, match=r"裝置容量\(瓩\)"):
        normalize(tmp_path)


def test_cli_missing_column_exits_nonzero(tmp_path, capsys):
    write_snapshot(tmp_path / "snap")
    (tmp_path / "snap" / "thermal_hydro.csv").write_text("電廠名稱\n", encoding="utf-8")
    assert main(["normalize", "--raw-dir", str(tmp_path / "snap"), "--output", str(tmp_path / "o.json")]) == 1
    assert "裝置容量(瓩)" in capsys.readouterr().err


# --- Official fuel mapping and primary energy ------------------------------------------


@pytest.mark.parametrize("value,category,recognized", [
    ("水", "hydro", True),
    ("煤", "coal", True),
    ("天然氣", "gas", True),
    ("民營電廠-燃煤", "coal", True),
    ("重油", "other", True),
    ("輕柴油", "other", True),
    ("離岸風力/Offshore Wind", "wind", True),
    ("生質能", "other", False),
])
def test_fuel_mapping(value, category, recognized):
    assert map_fuel(value) == (category, recognized)


def test_unrecognized_fuel_warns(tmp_path):
    result = normalize(write_snapshot(tmp_path, thermal=[th_row("某電廠", "台中市", "1", 1000, "生質能")]))
    assert any("生質能" in w for w in result["warnings"])


def test_mixed_fuel_primary_is_larger(tmp_path):
    rows = [th_row("興達發電廠", "高雄市永安區", "興三機", 550000, "煤"),
            th_row("興達發電廠", "高雄市永安區", "興四機", 550000, "煤")]
    rows += [th_row("興達發電廠", "高雄市永安區", f"複{i}機", 445190, "天然氣") for i in range(1, 6)]
    plant = by_id(normalize(write_snapshot(tmp_path, thermal=rows)))["tp-plant:興達發電廠"]
    assert plant["capacity_by_source_mw"] == {"coal": 1100.0, "gas": 2225.95}
    assert plant["energy_primary"] == "gas"


def test_primary_tie_follows_category_order(tmp_path):
    rows = [th_row("X電廠", "台中市", "1", 1000, "煤"), th_row("X電廠", "台中市", "2", 1000, "天然氣")]
    assert by_id(normalize(write_snapshot(tmp_path, thermal=rows)))["tp-plant:X電廠"]["energy_primary"] == "gas"


# --- Official scope filter ---------------------------------------------------------------


def test_outlying_island_plants_excluded(tmp_path):
    rows = [th_row("塔山發電廠", "金門縣金湖鎮", "1", 1000, "重油"),
            th_row("協和電廠－珠山分廠", "連江縣南竿鄉", "1", 1000, "重油"),
            th_row("尖山發電廠", "澎湖縣湖西鄉", "1", 1000, "重油"),
            th_row("臺中發電廠", "臺中市龍井區", "1", 1000, "煤")]
    result = normalize(write_snapshot(tmp_path, thermal=rows))
    assert list(by_id(result)) == ["tp-plant:臺中發電廠"]
    assert result["excluded_outside_main_island"] == 3
    assert by_id(result)["tp-plant:臺中發電廠"]["county"] == "台中市"


def test_units_json_without_aadata_rejected(tmp_path):
    root = write_snapshot(tmp_path)
    (root / "units.json").write_text(json.dumps({"data": []}), encoding="utf-8")
    with pytest.raises(OfficialDataError, match="aaData"):
        normalize(root)


def test_units_json_row_missing_column_rejected(tmp_path):
    units = [unit("民營電廠-燃氣", "海湖#1", "450.0"), {"機組類型": "民營電廠-燃氣"}]
    with pytest.raises(OfficialDataError, match="row 1: missing column"):
        normalize(write_snapshot(tmp_path, units=units))
