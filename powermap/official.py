"""Download and normalize Taipower open data from data.gov.tw.

Implements the ``official-power-data`` spec.

Usage::

    python -m powermap.official download --dest data/official/raw
    python -m powermap.official normalize [--raw-dir data/official/raw/2026-11-12] \
        --output data/interim/official_plants.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from powermap.crosswalk import chinese_part, normalize_name
from powermap.parsers import SOURCE_CATEGORIES

LICENSE = "政府資料開放授權條款第1版"
DEFAULT_RAW_ROOT = Path("data/official/raw")
EXCLUDED_COUNTIES = ("金門縣", "連江縣", "澎湖縣")
USER_AGENT = "powermap/0.1 (open data pipeline)"
_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    title: str
    url: str
    file: str


DATASETS = (
    Dataset("8934", "台灣電力公司水火力發電廠位置及機組設備",
            "https://service.taipower.com.tw/data/opendata/apply/file/d004011/001.csv", "thermal_hydro.csv"),
    Dataset("10858", "台灣電力公司核能發電廠位置及機組設備",
            "https://service.taipower.com.tw/data/opendata/apply/file/d056001/001.csv", "nuclear.csv"),
    Dataset("17141", "台灣電力公司再生能源各場址資料",
            "https://service.taipower.com.tw/data/opendata/apply/file/d693002/001.csv", "renewable.csv"),
    Dataset("8931", "台灣電力公司各機組發電量即時資訊(含外購電力)",
            "https://service.taipower.com.tw/data/opendata/apply/file/d006001/001.json", "units.json"),
)


class OfficialDataError(Exception):
    """Raised when an official file does not have the expected shape."""


# --- Download -------------------------------------------------------------------


def download(dest_root: str | Path, datasets: tuple[Dataset, ...] = DATASETS, now: datetime | None = None) -> Path:
    """Download all datasets into ``dest_root/<YYYY-MM-DD>/``; all-or-nothing."""
    now = now or datetime.now(timezone.utc)
    dest_root = Path(dest_root)
    target = dest_root / now.strftime("%Y-%m-%d")
    if target.exists():
        raise FileExistsError(f"snapshot directory already exists: {target}")
    dest_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".download-", dir=dest_root))
    try:
        files = []
        for ds in datasets:
            request = urllib.request.Request(ds.url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            (tmp / ds.file).write_bytes(data)
            files.append({"dataset_id": ds.dataset_id, "title": ds.title, "url": ds.url, "file": ds.file,
                          "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        manifest = {"downloaded_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "license": LICENSE, "files": files}
        (tmp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.chmod(0o755)  # mkdtemp creates 0700
        tmp.rename(target)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return target


def latest_snapshot(raw_root: str | Path = DEFAULT_RAW_ROOT) -> Path:
    dirs = sorted(p for p in Path(raw_root).iterdir() if p.is_dir() and _DATE_DIR_RE.match(p.name))
    if not dirs:
        raise OfficialDataError(f"no snapshot directory under {raw_root}; run `make official-download`")
    return dirs[-1]


# --- Normalization ----------------------------------------------------------------

_FUEL_MAP = {
    "水": "hydro",
    "煤": "coal",
    "燃煤": "coal",
    "天然氣": "gas",
    "燃氣": "gas",
    "核能": "nuclear",
    "太陽能": "solar",
    "陸域風力": "wind",
    "離岸風力": "wind",
    "地熱": "geothermal",
    "重油": "other",
    "輕柴油": "other",
    "燃料油": "other",
}


def map_fuel(value: str) -> tuple[str, bool]:
    """Return ``(category, recognized)`` for an official fuel or energy type."""
    text = value.split("/", 1)[0].strip()
    text = text.removeprefix("民營電廠-")
    if text in _FUEL_MAP:
        return _FUEL_MAP[text], True
    return "other", False


def primary_energy(capacity_by_source: dict[str, float]) -> str | None:
    """Category with the largest capacity; ties follow ``SOURCE_CATEGORIES`` order."""
    best = None
    for category in SOURCE_CATEGORIES:
        if category in capacity_by_source and (best is None or capacity_by_source[category] > capacity_by_source[best]):
            best = category
    return best


def county_of(address: str | None) -> str | None:
    if not address or not address.strip():
        return None
    return address.strip().replace("臺", "台")[:3]


class _PlantBuilder:
    """Accumulates units into plant records."""

    def __init__(self) -> None:
        self.plants: dict[str, dict] = {}
        self.warnings: list[str] = []

    def add_unit(self, official_id: str, dataset_id: str, name: str, address: str | None,
                 fuel: str | None, capacity_mw: float | None, category: str | None = None) -> None:
        plant = self.plants.get(official_id)
        if plant is None:
            plant = self.plants[official_id] = {
                "official_id": official_id, "dataset_id": dataset_id, "name": name,
                "name_normalized": normalize_name(name), "county": county_of(address),
                "address": address.strip() if address and address.strip() else None,
                "capacity_by_source_mw": defaultdict(float), "n_units": 0,
            }
        elif plant["address"] is None and address and address.strip():
            plant["address"], plant["county"] = address.strip(), county_of(address)
        if category is None:
            category, recognized = map_fuel(fuel or "")
            if not recognized:
                self.warnings.append(f"{official_id}: unrecognized fuel '{fuel}' mapped to other")
        plant["n_units"] += 1
        if capacity_mw is None:
            self.warnings.append(f"{official_id}: unit without capacity")
            capacity_mw = 0.0
        plant["capacity_by_source_mw"][category] += capacity_mw

    def finish(self) -> list[dict]:
        out = []
        for plant in sorted(self.plants.values(), key=lambda p: p["official_id"]):
            by_source = {k: round(v, 3) for k, v in plant["capacity_by_source_mw"].items()}
            out.append({
                "official_id": plant["official_id"], "dataset_id": plant["dataset_id"], "name": plant["name"],
                "name_normalized": plant["name_normalized"], "county": plant["county"], "address": plant["address"],
                "capacity_mw": round(sum(by_source.values()), 3), "capacity_by_source_mw": by_source,
                "energy_primary": primary_energy(by_source), "n_units": plant["n_units"],
            })
        return out


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _read_csv(path: Path, required: tuple[str, ...]) -> list[dict]:
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig")))
    missing = [c for c in required if c not in (reader.fieldnames or [])]
    if missing:
        raise OfficialDataError(f"{path.name}: missing column(s): {', '.join(missing)}")
    return list(reader)


TH_COLS = ("電廠名稱", "地址-縣市鄉鎮", "地址-村里", "地址-街路門牌", "裝置容量(瓩)", "燃料種類")
NU_COLS = ("電廠名稱", "地址", "裝置容量MWe")
RE_COLS = ("能源別/Type of Energy", "發電站名稱/Name of The Power Station", "裝置容量(瓩)/Installed Capacity(kW)", "地址/Address")
UNIT_KEYS = ("機組類型", "機組名稱", "裝置容量(MW)")


def _kw_to_mw(value: str | None) -> float | None:
    kw = _number(value)
    return None if kw is None else kw / 1000


def normalize(raw_dir: str | Path) -> dict:
    """Turn one snapshot directory into the plant-level official list."""
    raw_dir = Path(raw_dir)
    b = _PlantBuilder()

    for row in _read_csv(raw_dir / "thermal_hydro.csv", TH_COLS):
        name = row["電廠名稱"].strip()
        if not name:
            continue
        address = "".join(row[c].strip() for c in ("地址-縣市鄉鎮", "地址-村里", "地址-街路門牌"))
        b.add_unit(f"tp-plant:{name}", "8934", name, address, row["燃料種類"], _kw_to_mw(row["裝置容量(瓩)"]))

    for row in _read_csv(raw_dir / "nuclear.csv", NU_COLS):
        name = row["電廠名稱"].strip()
        if not name:
            continue
        b.add_unit(f"tp-plant:{name}", "10858", name, row["地址"], None, _number(row["裝置容量MWe"]), category="nuclear")

    for row in _read_csv(raw_dir / "renewable.csv", RE_COLS):
        energy = (row["能源別/Type of Energy"] or "").strip()
        station = chinese_part(row["發電站名稱/Name of The Power Station"] or "")
        if not energy or not station:
            continue
        b.add_unit(f"tp-re:{station}", "17141", station, row["地址/Address"], energy,
                   _kw_to_mw(row["裝置容量(瓩)/Installed Capacity(kW)"]))

    units = json.loads((raw_dir / "units.json").read_text(encoding="utf-8-sig")).get("aaData", [])
    if units:
        missing = [k for k in UNIT_KEYS if k not in units[0]]
        if missing:
            raise OfficialDataError(f"units.json: missing column(s): {', '.join(missing)}")
    for row in units:
        unit_type, unit_name = row["機組類型"].strip(), row["機組名稱"].strip()
        if not unit_type.startswith("民營電廠-") or unit_name == "小計":
            continue
        name = unit_name.split("#", 1)[0].strip()
        b.add_unit(f"ipp:{name}", "8931", name, None, unit_type, _number(row["裝置容量(MW)"]))

    plants, excluded = [], 0
    for plant in b.finish():
        if plant["county"] in EXCLUDED_COUNTIES:
            excluded += 1
        else:
            plants.append(plant)
    return {"source_dir": raw_dir.as_posix(), "excluded_outside_main_island": excluded,
            "plants": plants, "warnings": b.warnings}


# --- CLI ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_dl = sub.add_parser("download", help="download a dated snapshot")
    p_dl.add_argument("--dest", default=str(DEFAULT_RAW_ROOT))
    p_norm = sub.add_parser("normalize", help="build official_plants.json")
    p_norm.add_argument("--raw-dir", help="snapshot directory (default: latest)")
    p_norm.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "download":
            target = download(args.dest)
            for entry in json.loads((target / "manifest.json").read_text(encoding="utf-8"))["files"]:
                print(f"{entry['file']:<18} {entry['bytes']:>8} bytes  sha256 {entry['sha256'][:16]}…")
            print(f"Saved {target}")
            return 0
        raw_dir = Path(args.raw_dir) if args.raw_dir else latest_snapshot()
        result = normalize(raw_dir)
    except (FileExistsError, OfficialDataError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    by_dataset = defaultdict(int)
    for plant in result["plants"]:
        by_dataset[plant["dataset_id"]] += 1
    print(f"Official plants: {len(result['plants'])} from {raw_dir} "
          f"({', '.join(f'{k}: {v}' for k, v in sorted(by_dataset.items()))}); "
          f"excluded outside main island: {result['excluded_outside_main_island']}")
    for warning in result["warnings"]:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
