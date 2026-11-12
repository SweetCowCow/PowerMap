"""Enrich OSM facilities with official plants through the reviewed crosswalk.

Implements the ``official-crosswalk`` spec (official enrichment, discrepancy and
unmatched reports) and the final ``plants.geojson`` of ``power-facility-dataset``.

Usage::

    python -m powermap.enrich --facilities data/interim/facilities_osm.geojson \
        --dedup-log-osm data/interim/dedup_log_osm.csv \
        --official data/interim/official_plants.json \
        --crosswalk data/official/crosswalk.csv \
        --output data/processed/plants.geojson --dedup-log data/processed/dedup_log.csv \
        --unmatched data/processed/unmatched.csv --diff data/processed/official_diff.csv \
        --meta data/interim/enrich_meta.json [--capacity-diff-threshold 0.2]
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import Point

from powermap.crosswalk import Crosswalk, CrosswalkError, load_crosswalk
from powermap.facilities import DEDUP_LOG_HEADER
from powermap.geo import to_3826

UNMATCHED_HEADER = ("official_id", "name", "county", "capacity_mw", "reason")
DIFF_HEADER = ("official_id", "osm_id", "osm_capacity_mw", "official_capacity_mw", "diff_ratio")
DEFAULT_THRESHOLD = 0.2


@dataclass
class EnrichResult:
    features: list[dict]
    log: list[dict]  # official merge rows only
    diff: list[dict] = field(default_factory=list)
    unmatched: list[dict] = field(default_factory=list)


def _distance_m(a: dict, b: dict) -> float:
    pa, pb = (to_3826(Point(f["geometry"]["coordinates"])) for f in (a, b))
    return round(pa.distance(pb), 1)


def _tag_official(props: dict, plant: dict) -> None:
    props["official_id"] = plant["official_id"]
    props["energy_primary"] = plant["energy_primary"]
    props["energy_primary_source"] = "taipower"


def enrich(features: list[dict], official_plants: list[dict], crosswalk: Crosswalk,
           threshold: float = DEFAULT_THRESHOLD) -> EnrichResult:
    features = copy.deepcopy(features)
    by_id = {f["properties"]["osm_id"]: f for f in features}
    plants = {p["official_id"]: p for p in official_plants}
    dropped: set[str] = set()
    result = EnrichResult([], [])

    for official_id in sorted(crosswalk.links):
        link, plant = crosswalk.links[official_id], plants[official_id]
        if link.relation == "none":
            continue
        if link.relation == "part":
            for osm_id in link.osm_ids:
                _tag_official(by_id[osm_id]["properties"], plant)
            continue
        kept, *others = (by_id[i] for i in link.osm_ids)
        props = kept["properties"]
        for other in others:
            props["n_generators"] += other["properties"]["n_generators"]
            dropped.add(other["properties"]["osm_id"])
            result.log.append({"action": "official_same_plant", "kept_osm_id": props["osm_id"],
                               "dropped_osm_id": other["properties"]["osm_id"], "reason": official_id,
                               "distance_m": _distance_m(kept, other)})
        _tag_official(props, plant)
        official_mw = plant["capacity_mw"]
        if props["capacity_mw"] is None:
            props.update(capacity_mw=official_mw, capacity_source="taipower", missing_capacity=False)
        elif official_mw:
            ratio = abs(props["capacity_mw"] - official_mw) / official_mw
            if ratio > threshold:
                result.diff.append({"official_id": official_id, "osm_id": props["osm_id"],
                                    "osm_capacity_mw": props["capacity_mw"], "official_capacity_mw": official_mw,
                                    "diff_ratio": round(ratio, 3)})

    result.features = [f for f in features if f["properties"]["osm_id"] not in dropped]
    osm_missing = set(crosswalk.osm_missing)
    for plant in official_plants:
        link = crosswalk.links.get(plant["official_id"])
        if link is not None and link.relation != "none":
            continue
        reason = "no_osm" if link else "osm_missing" if plant["official_id"] in osm_missing else "unreviewed"
        result.unmatched.append({"official_id": plant["official_id"], "name": plant["name"],
                                 "county": plant["county"] or "", "capacity_mw": plant["capacity_mw"],
                                 "reason": reason})
    return result


def _write_csv(path: str | Path, header: tuple[str, ...], rows: list[dict]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("facilities", "dedup-log-osm", "official", "crosswalk", "output", "dedup-log", "unmatched",
                 "diff", "meta"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--capacity-diff-threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)

    features = json.loads(Path(args.facilities).read_text(encoding="utf-8"))["features"]
    official = json.loads(Path(args.official).read_text(encoding="utf-8"))
    try:
        crosswalk = load_crosswalk(args.crosswalk, {p["official_id"] for p in official["plants"]},
                                   {f["properties"]["osm_id"] for f in features})
    except CrosswalkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    result = enrich(features, official["plants"], crosswalk, args.capacity_diff_threshold)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"type": "FeatureCollection", "features": result.features}, ensure_ascii=False),
                      encoding="utf-8")
    with Path(args.dedup_log_osm).open(encoding="utf-8", newline="") as fh:
        osm_log = list(csv.DictReader(fh))
    _write_csv(args.dedup_log, DEDUP_LOG_HEADER, osm_log + result.log)
    _write_csv(args.unmatched, UNMATCHED_HEADER, result.unmatched)
    _write_csv(args.diff, DIFF_HEADER, result.diff)
    unreviewed = sum(1 for r in result.unmatched if r["reason"] == "unreviewed")
    meta = {"capacity_diff_threshold": args.capacity_diff_threshold, "unreviewed": unreviewed,
            "ignored_crosswalk_ids": crosswalk.ignored_ids, "warnings": crosswalk.warnings}
    Path(args.meta).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    filled = sum(1 for f in result.features if f["properties"]["capacity_source"] == "taipower")
    print(f"Enriched facilities: {len(result.features)} (official merges: {len(result.log)}, "
          f"capacity filled: {filled}, discrepancies: {len(result.diff)}, unmatched official: {len(result.unmatched)})")
    print(f"Unreviewed official plants: {unreviewed}; ignored crosswalk ids: {crosswalk.ignored_ids}")
    for warning in crosswalk.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
