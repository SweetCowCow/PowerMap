"""Extract OSM power features into line-delimited GeoJSON.

Implements the ``osm-power-extraction`` spec: power feature extraction,
snapshot timestamp recording, main island scope filter and extraction summary.

Usage::

    python -m powermap.extract --input data/raw/taiwan-latest.osm.pbf \
        --output data/interim/power.geojsonseq \
        --summary data/interim/extract_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import osmium
from shapely.geometry import MultiPolygon, box, mapping, shape

from powermap.parsers import classify_energy

POWER_VALUES = ("plant", "generator", "line", "minor_line", "cable")
FACILITY_VALUES = ("plant", "generator")
LINE_VALUES = ("line", "minor_line", "cable")

#: (min_lon, min_lat, max_lon, max_lat). West edge 119.3 keeps Changhua
#: offshore wind farms (lon 119.8–119.9); Penghu is removed separately.
DEFAULT_MAIN_BBOX = (119.3, 21.8, 122.2, 25.4)
#: Checked in this order; Penghu requires full containment, the others intersection.
EXCLUDED_REGIONS = {
    "penghu": (119.3, 23.1, 119.75, 23.8),
    "kinmen": (118.1, 24.3, 118.5, 24.6),
    "matsu": (119.9, 25.9, 120.6, 26.4),
}
REGION_NAMES = tuple(EXCLUDED_REGIONS) + ("other",)

_PREFIX = {"node": "n", "way": "w", "relation": "r"}


def osm_ref(osm_type: str, osm_id: int) -> str:
    """Return the short id used in reports, e.g. ``w123``."""
    return f"{_PREFIX[osm_type]}{osm_id}"


class ScopeFilter:
    """Main island scope filter (see spec 'Main island scope filter')."""

    def __init__(self, main_bbox: tuple[float, float, float, float] = DEFAULT_MAIN_BBOX):
        self.main = box(*main_bbox)
        self.regions = {name: box(*bb) for name, bb in EXCLUDED_REGIONS.items()}

    def region_of(self, geom) -> str | None:
        """Return ``None`` when the geometry is kept, else its excluded region."""
        within_penghu = geom.within(self.regions["penghu"])
        if geom.intersects(self.main) and not within_penghu:
            return None
        if within_penghu:
            return "penghu"
        for name in ("kinmen", "matsu"):
            if geom.intersects(self.regions[name]):
                return name
        return "other"


@dataclass
class ExtractResult:
    snapshot: str | None
    features: list[dict]
    counts: dict[str, dict[str, int]]
    geometryless_relations: int
    mixed_energy_facilities: int
    excluded_by_region: dict[str, int]
    excluded_by_power: dict[str, int]
    excluded_other_ids: list[str]
    invalid_skipped: int
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "snapshot": self.snapshot,
            "kept_by_power_and_geometry": self.counts,
            "kept_total": len(self.features),
            "geometryless_relations": self.geometryless_relations,
            "mixed_energy_facilities": self.mixed_energy_facilities,
            "excluded_by_region": self.excluded_by_region,
            "excluded_by_power": self.excluded_by_power,
            "excluded_other_ids": self.excluded_other_ids,
            "invalid_skipped": self.invalid_skipped,
            "warnings": self.warnings,
        }


def _normalize_polygon(geom):
    """A single-part MultiPolygon becomes a Polygon."""
    if isinstance(geom, MultiPolygon) and len(geom.geoms) == 1:
        return geom.geoms[0]
    return geom


def read_snapshot_timestamp(path: str | Path) -> str | None:
    value = osmium.io.Reader(str(path), osmium.osm.osm_entity_bits.NOTHING).header().get(
        "osmosis_replication_timestamp"
    )
    return value or None


def extract(path: str | Path, scope: ScopeFilter | None = None) -> ExtractResult:
    """Read an OSM file and return kept power features plus summary data."""
    scope = scope or ScopeFilter()
    factory = osmium.geom.GeoJSONFactory()
    warnings: list[str] = []

    snapshot = read_snapshot_timestamp(path)
    if snapshot is None:
        warnings.append("snapshot timestamp missing in pbf header (osmosis_replication_timestamp)")

    candidates: list[tuple[str, int, dict, object]] = []  # (osm_type, id, tags, geometry)
    pending_closed_ways: dict[int, tuple[dict, object]] = {}
    area_way_ids: set[int] = set()
    geometryless_relations = 0
    invalid = 0

    processor = (
        osmium.FileProcessor(str(path))
        .with_filter(osmium.filter.KeyFilter("power"))
        .with_areas(osmium.filter.TagFilter(("power", "plant"), ("power", "generator")))
    )
    for obj in processor:
        tags = dict(obj.tags)
        power = tags.get("power")
        if power not in POWER_VALUES:
            continue
        try:
            if obj.is_node():
                geom = shape(json.loads(factory.create_point(obj)))
                candidates.append(("node", obj.id, tags, geom))
            elif obj.is_way():
                geom = shape(json.loads(factory.create_linestring(obj)))
                if power in FACILITY_VALUES and obj.is_closed():
                    # Wait for the assembled area; fall back to the line if none comes.
                    pending_closed_ways[obj.id] = (tags, geom)
                else:
                    candidates.append(("way", obj.id, tags, geom))
            elif obj.is_area():
                if power not in FACILITY_VALUES:
                    continue
                geom = _normalize_polygon(shape(json.loads(factory.create_multipolygon(obj))))
                if obj.from_way():
                    area_way_ids.add(obj.orig_id())
                    candidates.append(("way", obj.orig_id(), tags, geom))
                else:
                    candidates.append(("relation", obj.orig_id(), tags, geom))
            elif obj.is_relation():
                is_multipolygon = tags.get("type") == "multipolygon"
                if not (is_multipolygon and power in FACILITY_VALUES):
                    geometryless_relations += 1
        except (osmium.InvalidLocationError, RuntimeError, ValueError):
            invalid += 1

    for way_id, (tags, geom) in pending_closed_ways.items():
        if way_id not in area_way_ids:
            candidates.append(("way", way_id, tags, geom))

    features: list[dict] = []
    counts: dict[str, Counter] = defaultdict(Counter)
    excluded_by_region = {name: 0 for name in REGION_NAMES}
    excluded_by_power = {value: 0 for value in POWER_VALUES}
    excluded_other_ids: list[str] = []
    mixed = 0

    for osm_type, osm_id, tags, geom in sorted(candidates, key=lambda c: (c[0], c[1])):
        if geom.is_empty or not geom.is_valid:
            invalid += 1
            continue
        power = tags["power"]
        region = scope.region_of(geom)
        if region is not None:
            excluded_by_region[region] += 1
            excluded_by_power[power] += 1
            if region == "other":
                excluded_other_ids.append(osm_ref(osm_type, osm_id))
            continue
        counts[power][geom.geom_type] += 1
        if power in FACILITY_VALUES and classify_energy(tags.get(f"{power}:source"))[0] == "mixed":
            mixed += 1
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {"osm_type": osm_type, "osm_id": osm_id, "tags": tags},
            }
        )

    return ExtractResult(
        snapshot=snapshot,
        features=features,
        counts={p: dict(c) for p, c in sorted(counts.items())},
        geometryless_relations=geometryless_relations,
        mixed_energy_facilities=mixed,
        excluded_by_region=excluded_by_region,
        excluded_by_power=excluded_by_power,
        excluded_other_ids=excluded_other_ids,
        invalid_skipped=invalid,
        warnings=warnings,
    )


def write_geojsonseq(features: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for feature in features:
            fh.write(json.dumps(feature, ensure_ascii=False) + "\n")


def format_summary(summary: dict) -> str:
    lines = [f"Snapshot: {summary['snapshot']}", "", "Kept features (power × geometry):"]
    for power, by_geom in summary["kept_by_power_and_geometry"].items():
        parts = ", ".join(f"{g} {n}" for g, n in sorted(by_geom.items()))
        lines.append(f"  {power:<11} {sum(by_geom.values()):>7}  ({parts})")
    lines += [
        f"  {'total':<11} {summary['kept_total']:>7}",
        "",
        f"Multi-source (mixed) facilities: {summary['mixed_energy_facilities']}",
        f"Relations without geometry:      {summary['geometryless_relations']}",
        f"Invalid geometry skipped:        {summary['invalid_skipped']}",
        "",
        "Excluded outside main island:",
    ]
    for region, n in summary["excluded_by_region"].items():
        lines.append(f"  {region:<7} {n:>6}")
    by_power = ", ".join(f"{p} {n}" for p, n in summary["excluded_by_power"].items() if n)
    lines.append(f"  by power: {by_power or 'none'}")
    if summary["excluded_other_ids"]:
        lines.append(f"  'other' ids: {', '.join(summary['excluded_other_ids'])}")
    for warning in summary["warnings"]:
        lines.append(f"WARNING: {warning}")
    return "\n".join(lines)


def _parse_bbox(text: str) -> tuple[float, float, float, float]:
    values = tuple(float(v) for v in text.split(","))
    if len(values) != 4:
        raise argparse.ArgumentTypeError("bbox must be min_lon,min_lat,max_lon,max_lat")
    return values  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--main-bbox", type=_parse_bbox, default=DEFAULT_MAIN_BBOX)
    args = parser.parse_args(argv)

    result = extract(args.input, ScopeFilter(args.main_bbox))
    write_geojsonseq(result.features, args.output)
    summary = result.summary()
    Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(format_summary(summary))
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
