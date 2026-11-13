"""Build the substation point dataset from extracted ``power=substation`` features.

Implements the ``substation-dataset`` spec: one point per OSM object, areas converted with
``representative_point()``, voltage parsed and classified like lines. The only substations
removed are duplicates where one area lies inside another and one of them is unnamed or both
share a name ("Contained substation removal"); each removal is written to the dedup log.

Usage::

    python -m powermap.substations --input data/interim/power.geojsonseq \
        --output data/processed/substations.geojson \
        --dedup-log data/processed/substation_dedup_log.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

from powermap.geo import to_3826
from powermap.osm import osm_ref, osm_url, tag_text
from powermap.parsers import classify_voltage, parse_voltage_max_kv

DECIMALS = 5
PROPERTY_KEYS = (
    "osm_id",
    "osm_url",
    "name",
    "operator",
    "substation",
    "voltage_max_kv",
    "voltage_raw",
    "voltage_class",
    "voltage_source",
    "missing_voltage",
    "geom_src",
)
_TYPE_ORDER = {"node": 0, "way": 1, "relation": 2}
CONTAINED_SHARE = 0.9
DEDUP_LOG_HEADER = ("action", "kept_osm_id", "dropped_osm_id", "reason", "distance_m")


def substation_properties(osm_type: str, osm_id: int, tags: dict, geom_src: str) -> dict:
    kv = parse_voltage_max_kv(tags.get("voltage"))
    props = {
        "osm_id": osm_ref(osm_type, osm_id),
        "osm_url": osm_url(osm_type, osm_id),
        "name": tag_text(tags.get("name")) or tag_text(tags.get("name:zh")),
        "operator": tag_text(tags.get("operator")),
        "substation": tag_text(tags.get("substation")),
        "voltage_max_kv": kv,
        "voltage_raw": tag_text(tags.get("voltage")),
        "voltage_class": classify_voltage(kv),
        "voltage_source": None if kv is None else "osm",
        "missing_voltage": kv is None,
        "geom_src": geom_src,
    }
    return {key: props[key] for key in PROPERTY_KEYS}


def _areas_3826(geoms: list) -> list:
    """Polygons in EPSG:3826 (repaired with make_valid); ``None`` for points or unusable shapes."""
    out = []
    for geom in geoms:
        if geom.geom_type not in ("Polygon", "MultiPolygon"):
            out.append(None)
            continue
        projected = to_3826(geom if geom.is_valid else shapely.make_valid(geom))
        out.append(projected if projected.area > 0 else None)
    return out


def contained_removals(names: list[str | None], geoms: list) -> dict[int, tuple[int, str]]:
    """Index of each substation to drop -> (index of the substation kept in its pair, reason).

    A is contained in B when at least 90% of A's area lies in B and A is smaller than B
    (EPSG:3826); B is the smallest such container. When only one of the pair has a name, the
    unnamed one is dropped (inner or outer); when both are unnamed or share a name, A is dropped;
    different names keep both. A substation is dropped at most once, first pair in sort order wins.
    """
    areas = _areas_3826(geoms)
    indexed = [i for i, a in enumerate(areas) if a is not None]
    tree = STRtree([areas[i] for i in indexed])
    removals: dict[int, tuple[int, str]] = {}
    for i in indexed:
        inner = areas[i]
        containers = []
        for k in tree.query(inner):
            j = indexed[k]
            outer = areas[j]
            if j == i or outer.area <= inner.area:
                continue
            if inner.intersection(outer).area >= CONTAINED_SHARE * inner.area:
                containers.append(j)
        if not containers:
            continue
        j = min(containers, key=lambda c: areas[c].area)
        if names[i] is not None and names[j] is None:
            drop, keep, reason = j, i, "unnamed"
        elif names[i] is None:
            drop, keep, reason = i, j, "unnamed"
        elif names[i] == names[j]:
            drop, keep, reason = i, j, "same_name"
        else:
            continue
        if drop not in removals:
            removals[drop] = (keep, reason)
    # A kept substation may itself be dropped by another pair: record the one that finally stays.
    for drop, (keep, reason) in list(removals.items()):
        seen = {drop}
        while keep in removals and keep not in seen:
            seen.add(keep)
            keep = removals[keep][0]
        removals[drop] = (keep, reason)
    return removals


def build_substations_with_log(features: list[dict]) -> tuple[list[dict], list[dict]]:
    """Point features for ``power=substation`` (sorted by OSM id) and the dedup log rows."""
    selected = [f for f in features if f["properties"]["tags"].get("power") == "substation"]
    selected.sort(key=lambda f: (_TYPE_ORDER[f["properties"]["osm_type"]], f["properties"]["osm_id"]))
    geoms = [shape(f["geometry"]) for f in selected]
    points = [g if g.geom_type == "Point" else g.representative_point() for g in geoms]
    props = [substation_properties(f["properties"]["osm_type"], f["properties"]["osm_id"], f["properties"]["tags"],
                                   g.geom_type) for f, g in zip(selected, geoms)]
    removals = contained_removals([p["name"] for p in props], geoms)

    out, log = [], []
    for i, (point, p) in enumerate(zip(points, props)):
        if i in removals:
            j, reason = removals[i]
            distance = to_3826(point).distance(to_3826(points[j]))
            log.append({"action": "substation_contained", "kept_osm_id": props[j]["osm_id"],
                        "dropped_osm_id": p["osm_id"], "reason": reason, "distance_m": round(distance, 1)})
            continue
        out.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(point.x, DECIMALS), round(point.y, DECIMALS)]},
            "properties": p,
        })
    return out, log


def build_substations(features: list[dict]) -> list[dict]:
    """Return Point features for ``power=substation`` features, sorted by OSM id."""
    return build_substations_with_log(features)[0]


def write_dedup_log(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=DEDUP_LOG_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_features(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dedup-log", required=True)
    args = parser.parse_args(argv)

    features, log = build_substations_with_log(read_features(args.input))
    write_dedup_log(args.dedup_log, log)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    missing = sum(f["properties"]["missing_voltage"] for f in features)
    print(f"Substations: {len(features)} ({missing} without voltage; {len(log)} contained duplicates removed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
