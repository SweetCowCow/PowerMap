"""Tests for powermap.official_status (spec: official-status)."""

import csv
import json

import pytest

from powermap.official_status import STATUS_HEADER, StatusError, build, load_status, main

OFFICIAL_IDS = {"tp-plant:核一廠", "tp-plant:龍門廠", "tp-plant:協和發電廠"}
CHINSHAN = ["tp-plant:核一廠", "retired", "2019-07", "一號機 2018-12 停機；二號機 2019-07 停機",
            "https://www.taipower.com.tw/example", "2026-11-13", ""]
LUNGMEN = ["tp-plant:龍門廠", "mothballed", "", "", "https://example.org/lungmen", "2026-11-13", "未曾商轉"]


def write_csv(path, rows, header=STATUS_HEADER):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def load(tmp_path, rows):
    return load_status(write_csv(tmp_path / "status.csv", rows), OFFICIAL_IDS)


def with_cell(row, column, value):
    out = list(row)
    out[STATUS_HEADER.index(column)] = value
    return out


# --- Official status table validation: example table ----------------------------------


def test_duplicate_official_id_prints_both_rows(tmp_path):
    with pytest.raises(StatusError) as exc:
        load(tmp_path, [CHINSHAN, with_cell(CHINSHAN, "since", "2019")])
    assert "appears on lines [2, 3]" in str(exc.value)
    assert "2019-07" in str(exc.value) and ",2019," in str(exc.value)


@pytest.mark.parametrize("column, value, message", [
    ("status", "closed", "status 'closed'"),
    ("since", "2019/07", "since '2019/07'"),
    ("source", "台電新聞稿", "source '台電新聞稿'"),
    ("checked_at", "2026-11", "checked_at '2026-11'"),
])
def test_invalid_cell_exits_with_row(tmp_path, column, value, message):
    with pytest.raises(StatusError, match=rf"line 2: .*{message}.*核一廠"):
        load(tmp_path, [with_cell(CHINSHAN, column, value)])


def test_unknown_official_id_is_ignored_with_warning(tmp_path):
    table = load(tmp_path, [with_cell(CHINSHAN, "official_id", "tp-plant:不存在"), LUNGMEN])
    assert [r["official_id"] for r in table.rows] == ["tp-plant:龍門廠"]
    assert table.warnings == ["line 2: tp-plant:不存在 is not in the official list; row ignored"]


@pytest.mark.parametrize("since", ["", "2019", "2019-07", "2019-07-15"])
def test_valid_since_forms(tmp_path, since):
    assert load(tmp_path, [with_cell(CHINSHAN, "since", since)]).rows[0]["since"] == since


def test_missing_column(tmp_path):
    path = write_csv(tmp_path / "status.csv", [], header=STATUS_HEADER[:-1])
    with pytest.raises(StatusError, match="missing column"):
        load_status(path, OFFICIAL_IDS)


# --- Official status output --------------------------------------------------------------


def test_retired_nuclear_plant_example(tmp_path):
    status = build(load(tmp_path, [CHINSHAN]))
    assert status == {"tp-plant:核一廠": {
        "status": "retired", "since": "2019-07", "units": "一號機 2018-12 停機；二號機 2019-07 停機",
        "source": "https://www.taipower.com.tw/example", "checked_at": "2026-11-13", "note": None}}
    assert list(status["tp-plant:核一廠"]) == ["status", "since", "units", "source", "checked_at", "note"]


def test_keys_sorted_and_empty_cells_null(tmp_path):
    status = build(load(tmp_path, [LUNGMEN, CHINSHAN]))
    assert list(status) == sorted(["tp-plant:龍門廠", "tp-plant:核一廠"])
    assert status["tp-plant:龍門廠"]["since"] is None and status["tp-plant:龍門廠"]["units"] is None


def run_main(tmp_path, rows=None):
    official = tmp_path / "official_plants.json"
    official.write_text(json.dumps({"plants": [{"official_id": i} for i in OFFICIAL_IDS]}, ensure_ascii=False),
                        encoding="utf-8")
    status = tmp_path / "status.csv"
    if rows is not None:
        write_csv(status, rows)
    output = tmp_path / "out" / "official_status.json"
    code = main(["--official", str(official), "--status", str(status), "--output", str(output)])
    return code, output


def test_main_missing_table_writes_empty_object(tmp_path):
    code, output = run_main(tmp_path)
    assert code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {}


def test_main_writes_status(tmp_path):
    code, output = run_main(tmp_path, [CHINSHAN, LUNGMEN])
    assert code == 0
    assert list(json.loads(output.read_text(encoding="utf-8"))) == ["tp-plant:核一廠", "tp-plant:龍門廠"]


def test_main_invalid_table_exits_non_zero(tmp_path, capsys):
    code, output = run_main(tmp_path, [with_cell(CHINSHAN, "status", "closed")])
    assert code == 1
    assert not output.exists()
    assert "line 2" in capsys.readouterr().err
