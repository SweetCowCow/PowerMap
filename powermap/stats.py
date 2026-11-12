"""Summarize the facility and line datasets into ``stats.json``.

Implements the ``power-data-stats`` spec. Every count is computed from the
output files; nothing is estimated.

Usage::

    python -m powermap.stats --plants data/processed/plants.geojson \
        --lines data/processed/lines.geojson \
        --summary data/interim/extract_summary.json \
        --facilities-meta data/interim/facilities_meta.json \
        --output data/processed/stats.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from powermap.extract import REGION_NAMES
from powermap.parsers import ENERGY_CATEGORIES, SOURCE_CATEGORIES, VOLTAGE_CLASSES


def compute_stats(
    plants: list[dict],
    lines: list[dict],
    extract_summary: dict,
    facilities_meta: dict,
    built_at: datetime | None = None,
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
    return {
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
    return "\n".join(lines)


def _load_features(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["features"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plants", required=True)
    parser.add_argument("--lines", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--facilities-meta", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    stats = compute_stats(
        _load_features(args.plants),
        _load_features(args.lines),
        json.loads(Path(args.summary).read_text(encoding="utf-8")),
        json.loads(Path(args.facilities_meta).read_text(encoding="utf-8")),
    )
    Path(args.output).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(format_stats(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
