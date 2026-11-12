"""Summarize the facility and line datasets into ``stats.json``.

Implements the ``power-data-stats`` spec. Every count is computed from the
output files; nothing is estimated.

Usage::

    python -m powermap.stats --plants data/processed/plants.geojson \
        --lines data/processed/lines.geojson \
        --summary data/interim/extract_summary.json \
        --facilities-meta data/interim/facilities_meta.json \
        --official data/interim/official_plants.json \
        --dedup-log data/processed/dedup_log.csv \
        --diff data/processed/official_diff.csv \
        --unmatched data/processed/unmatched.csv \
        --output data/processed/stats.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from powermap.extract import REGION_NAMES
from powermap.parsers import ENERGY_CATEGORIES, SOURCE_CATEGORIES, VOLTAGE_CLASSES


UNMATCHED_REASONS = ("no_osm", "unreviewed", "osm_missing")


def compute_official(plants: list[dict], official: dict, dedup_rows: list[dict], diff_rows: list[dict],
                     unmatched_rows: list[dict]) -> dict:
    """Official cross-validation counts, all taken from the output files."""
    official_ids = [f["properties"]["official_id"] for f in plants if f["properties"].get("official_id")]
    return {
        "source_dir": official.get("source_dir"),
        "plants": len(official.get("plants", [])),
        "excluded_outside_main_island": official.get("excluded_outside_main_island", 0),
        "linked": len(set(official_ids)),
        "facilities_with_official_id": len(official_ids),
        "capacity_filled": sum(1 for f in plants if f["properties"]["capacity_source"] == "taipower"),
        "merged": sum(1 for r in dedup_rows if r["action"] == "official_same_plant"),
        "capacity_discrepancies": len(diff_rows),
        "unmatched": {reason: sum(1 for r in unmatched_rows if r["reason"] == reason) for reason in UNMATCHED_REASONS},
    }


def compute_stats(
    plants: list[dict],
    lines: list[dict],
    extract_summary: dict,
    facilities_meta: dict,
    built_at: datetime | None = None,
    official: dict | None = None,
) -> dict:
    by_energy = {key: 0 for key in ENERGY_CATEGORIES}
    by_source = {key: 0 for key in SOURCE_CATEGORIES}
    by_class = {key: 0 for key in VOLTAGE_CLASSES}
    for feature in plants:
        props = feature["properties"]
        by_energy[props["energy"]] += 1
        for source in props["energy_sources"]:
            by_source[source] += 1
    for feature in lines:
        by_class[feature["properties"]["voltage_class"]] += 1
    excluded = extract_summary.get("excluded_by_region", {})
    built_at = built_at or datetime.now(timezone.utc)
    stats = {
        "snapshot": extract_summary.get("snapshot"),
        "built_at": built_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "facilities": len(plants),
        "lines": len(lines),
        "lines_missing_voltage": sum(f["properties"]["missing_voltage"] for f in lines),
        "facilities_missing_capacity": sum(f["properties"]["missing_capacity"] for f in plants),
        "by_energy": by_energy,
        "by_energy_source": by_source,
        "by_voltage_class": by_class,
        "excluded_rooftop_solar": facilities_meta.get("excluded_rooftop_solar", 0),
        "excluded_outside_main_island": {region: excluded.get(region, 0) for region in REGION_NAMES},
    }
    if official is not None:
        stats["official"] = official
    return stats


def format_stats(stats: dict) -> str:
    excluded = ", ".join(f"{k} {v}" for k, v in stats["excluded_outside_main_island"].items())
    lines = [
        "=== Statistics ===",
        f"Snapshot:                    {stats['snapshot']}",
        f"Facilities:                  {stats['facilities']}",
        f"  missing capacity:          {stats['facilities_missing_capacity']}",
        f"  rooftop/small solar excl.: {stats['excluded_rooftop_solar']}",
        f"Lines:                       {stats['lines']}",
        f"  missing voltage:           {stats['lines_missing_voltage']}",
        f"Excluded outside main island (raw OSM features): {excluded}",
        "By energy:         " + ", ".join(f"{k} {v}" for k, v in stats["by_energy"].items()),
        "By energy source:  " + ", ".join(f"{k} {v}" for k, v in stats["by_energy_source"].items()),
        "By voltage class:  " + ", ".join(f"{k} {v}" for k, v in stats["by_voltage_class"].items()),
    ]
    if "official" in stats:
        o = stats["official"]
        lines += [
            f"Official plants:             {o['plants']} (linked {o['linked']}, capacity filled {o['capacity_filled']}, "
            f"merged {o['merged']}, discrepancies {o['capacity_discrepancies']})",
            "  unmatched:                 " + ", ".join(f"{k} {v}" for k, v in o["unmatched"].items()),
        ]
    return "\n".join(lines)


def _load_features(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["features"]


def _load_csv(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plants", required=True)
    parser.add_argument("--lines", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--facilities-meta", required=True)
    parser.add_argument("--official", required=True)
    parser.add_argument("--dedup-log", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--unmatched", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    plants = _load_features(args.plants)
    official = compute_official(
        plants,
        json.loads(Path(args.official).read_text(encoding="utf-8")),
        _load_csv(args.dedup_log),
        _load_csv(args.diff),
        _load_csv(args.unmatched),
    )
    stats = compute_stats(
        plants,
        _load_features(args.lines),
        json.loads(Path(args.summary).read_text(encoding="utf-8")),
        json.loads(Path(args.facilities_meta).read_text(encoding="utf-8")),
        official=official,
    )
    Path(args.output).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(format_stats(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
