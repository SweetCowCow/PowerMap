"""Build the power line dataset from extracted line, minor_line and cable ways.

Implements the ``power-line-dataset`` spec: one feature per OSM way, no merging,
10 m simplification in EPSG:3826 and coordinates rounded to 5 decimals.

Usage::

    python -m powermap.lines --input data/interim/power.geojsonseq \
        --output data/processed/lines.geojson
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import shape

from powermap.geo import to_3826, to_4326
from powermap.parsers import classify_voltage, parse_voltage_max_kv

LINE_KINDS = ("line", "minor_line", "cable")
SIMPLIFY_TOLERANCE_M = 10.0
DECIMALS = 5
PROPERTY_KEYS = (
    "osm_id",
    "osm_url",
    "kind",
    "voltage_max_kv",
    "voltage_raw",
    "voltage_class",
    "voltage_source",
    "missing_voltage",
    "location",
)
OSM_URL = "https://www.openstreetmap.org/way/{id}"


def _text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def simplify_line(geom) -> list[list[float]] | None:
    """Simplify in metres, return rounded lon/lat coordinates or ``None`` when unusable."""
    simplified = to_4326(to_3826(geom).simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True))
    if simplified.is_empty or simplified.geom_type != "LineString":
        return None
    coords: list[list[float]] = []
    for x, y in simplified.coords:
        point = [round(x, DECIMALS), round(y, DECIMALS)]
        if not coords or coords[-1] != point:
            coords.append(point)
    return coords if len(coords) >= 2 else None


def line_properties(osm_id: int, tags: dict) -> dict:
    kv = parse_voltage_max_kv(tags.get("voltage"))
    return {
        "osm_id": f"w{osm_id}",
        "osm_url": OSM_URL.format(id=osm_id),
        "kind": tags["power"],
        "voltage_max_kv": kv,
        "voltage_raw": tags.get("voltage"),
        "voltage_class": classify_voltage(kv),
        "voltage_source": None if kv is None else "osm",
        "missing_voltage": kv is None,
        "location": _text(tags.get("location")),
    }


def build_lines(features: list[dict]) -> tuple[list[dict], int]:
    """Return output features and the number of skipped (unusable) lines."""
    out: list[dict] = []
    skipped = 0
    for feature in features:
        props = feature["properties"]
        tags = props["tags"]
        if tags.get("power") not in LINE_KINDS or props["osm_type"] != "way":
            continue
        if feature["geometry"]["type"] != "LineString":
            continue
        coords = simplify_line(shape(feature["geometry"]))
        if coords is None:
            skipped += 1
            continue
        out.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": line_properties(props["osm_id"], tags),
            }
        )
    return out, skipped


def read_features(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    features, skipped = build_lines(read_features(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Lines: {len(features)}")
    if skipped:
        print(f"WARNING: skipped {skipped} lines with empty or invalid simplified geometry", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
