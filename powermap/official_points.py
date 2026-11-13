"""Turn the reviewed official location table into a point dataset for the web map.

Implements the ``official-locations`` spec. The positions in
``data/official/locations.csv`` are estimates from official addresses, reviewed by
hand; they are never mixed into the OSM facilities and ``unmatched.csv`` is not
touched.

Usage::

    python -m powermap.official_points --official data/interim/official_plants.json \
        --crosswalk data/official/crosswalk.csv --locations data/official/locations.csv \
        --output data/processed/official_points.geojson
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from powermap.extract import DEFAULT_MAIN_BBOX, _parse_bbox

LOCATION_HEADER = ("official_id", "lat", "lon", "precision", "method", "source", "checked_at", "note")
PRECISIONS = ("address", "parcel", "village", "road", "site", "offshore")
METHODS = ("nominatim", "manual")
DECIMALS = 5


class LocationError(Exception):
    """The location table has invalid rows; the pipeline must stop."""


@dataclass
class LocationTable:
    rows: list[dict] = field(default_factory=list)  # valid rows with float lat/lon
    warnings: list[str] = field(default_factory=list)


def _row_text(row: dict) -> str:
    return ",".join(row.get(c) or "" for c in LOCATION_HEADER)


def _coordinate(value: str | None) -> float | None:
    try:
        number = float(value or "")
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def load_locations(path: str | Path, official_ids: set[str], linked_ids: set[str],
                   bbox: tuple[float, float, float, float] = DEFAULT_MAIN_BBOX) -> LocationTable:
    """Read and check ``locations.csv``; a missing file is an empty table."""
    result = LocationTable()
    path = Path(path)
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in LOCATION_HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise LocationError(f"{path}: missing column(s): {', '.join(missing)}")
        rows = list(enumerate(reader, start=2))

    errors: list[str] = []
    lines_by_id: dict[str, list[int]] = {}
    for line, row in rows:
        lines_by_id.setdefault((row["official_id"] or "").strip(), []).append(line)
    text = {line: _row_text(row) for line, row in rows}
    for official_id, lines in lines_by_id.items():
        if len(lines) > 1:
            errors.append(f"official_id {official_id} appears on lines {lines}: "
                          + " | ".join(f"line {n}: {text[n]}" for n in lines))

    min_lon, min_lat, max_lon, max_lat = bbox
    valid: list[dict] = []
    for line, row in rows:
        problems = []
        precision, method = (row["precision"] or "").strip(), (row["method"] or "").strip()
        if precision not in PRECISIONS:
            problems.append(f"precision '{precision}' is not one of {', '.join(PRECISIONS)}")
        if method not in METHODS:
            problems.append(f"method '{method}' is not one of {', '.join(METHODS)}")
        lat, lon = _coordinate(row["lat"]), _coordinate(row["lon"])
        if lat is None or lon is None:
            problems.append(f"lat/lon '{row['lat']}', '{row['lon']}' is not a number")
        elif not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            problems.append(f"({lat}, {lon}) is outside the main island box {bbox}")
        if problems:
            errors.append(f"line {line}: {'; '.join(problems)}: {text[line]}")
            continue
        valid.append({**{c: (row[c] or "").strip() for c in LOCATION_HEADER}, "lat": lat, "lon": lon, "_line": line})
    if errors:
        raise LocationError(f"invalid locations in {path}:\n  " + "\n  ".join(errors))

    for row in valid:
        official_id, line = row["official_id"], row.pop("_line")
        if official_id not in official_ids:
            result.warnings.append(f"line {line}: {official_id} is not in the official list; row ignored")
        elif official_id in linked_ids:
            result.warnings.append(f"line {line}: {official_id} is linked to OSM in the crosswalk; row ignored")
        else:
            result.rows.append(row)
    return result


def linked_official_ids(crosswalk_path: str | Path) -> set[str]:
    """Official ids whose crosswalk relation is ``same`` or ``part``."""
    path = Path(crosswalk_path)
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {row["official_id"].strip() for row in csv.DictReader(fh)
                if (row.get("relation") or "").strip() in ("same", "part")}


def build(plants: list[dict], table: LocationTable) -> dict:
    by_id = {p["official_id"]: p for p in plants}
    features = []
    for row in sorted(table.rows, key=lambda r: r["official_id"]):
        plant = by_id[row["official_id"]]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [round(row["lon"], DECIMALS), round(row["lat"], DECIMALS)]},
            "properties": {
                "official_id": row["official_id"],
                "name": plant["name"],
                "county": plant.get("county"),
                "address": plant.get("address"),
                "capacity_mw": plant.get("capacity_mw"),
                "energy_primary": plant.get("energy_primary"),
                "precision": row["precision"],
                "method": row["method"],
                "source": row["source"],
                "checked_at": row["checked_at"],
            },
        })
    return {"type": "FeatureCollection", "features": features}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("official", "crosswalk", "locations", "output"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--main-bbox", type=_parse_bbox, default=DEFAULT_MAIN_BBOX)
    args = parser.parse_args(argv)

    plants = json.loads(Path(args.official).read_text(encoding="utf-8"))["plants"]
    try:
        table = load_locations(args.locations, {p["official_id"] for p in plants}, linked_official_ids(args.crosswalk),
                               args.main_bbox)
    except LocationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for warning in table.warnings:
        print(f"warning: {warning}", file=sys.stderr)

    collection = build(plants, table)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Official points: {len(collection['features'])} (ignored rows: {len(table.warnings)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
