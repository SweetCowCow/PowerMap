"""Build the facility point dataset from extracted plants and generators.

Implements the ``power-facility-dataset`` spec.

Usage::

    python -m powermap.facilities --input data/interim/power.geojsonseq \
        --output data/processed/plants.geojson \
        --dedup-log data/processed/dedup_log.csv \
        --meta data/interim/facilities_meta.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from shapely import STRtree
from shapely.geometry import Point, shape

from powermap.geo import to_3826
from powermap.osm import osm_ref, osm_url, tag_text
from powermap.parsers import classify_energy, parse_capacity_mw

PROPERTY_KEYS = (
    "osm_id",
    "osm_url",
    "kind",
    "name",
    "operator",
    "energy",
    "energy_sources",
    "energy_data_source",
    "source_raw",
    "capacity_mw",
    "capacity_raw",
    "capacity_source",
    "n_generators",
    "geom_src",
    "missing_capacity",
    "missing_energy",
)
DEDUP_LOG_HEADER = ("action", "kept_osm_id", "dropped_osm_id", "reason", "distance_m")


@dataclass
class Facility:
    osm_type: str
    osm_id: int
    kind: str
    tags: dict
    geometry: object  # source geometry, EPSG:4326
    point: Point = field(init=False)
    n_generators: int = 0

    def __post_init__(self) -> None:
        g = self.geometry
        self.point = g if g.geom_type == "Point" else g.representative_point()

    @property
    def ref(self) -> str:
        return osm_ref(self.osm_type, self.osm_id)

    @property
    def name(self) -> str | None:
        return tag_text(self.tags.get("name")) or tag_text(self.tags.get("name:zh"))

    @property
    def energy(self) -> tuple[str, list[str]]:
        return classify_energy(self.tags.get(f"{self.kind}:source"))

    @property
    def capacity_mw(self) -> float | None:
        return parse_capacity_mw(self.tags.get(f"{self.kind}:output:electricity"))

    def properties(self) -> dict:
        energy, sources = self.energy
        raw_source = tag_text(self.tags.get(f"{self.kind}:source"))
        raw_capacity = tag_text(self.tags.get(f"{self.kind}:output:electricity"))
        capacity = self.capacity_mw
        return {
            "osm_id": self.ref,
            "osm_url": osm_url(self.osm_type, self.osm_id),
            "kind": self.kind,
            "name": self.name,
            "operator": tag_text(self.tags.get("operator")),
            "energy": energy,
            "energy_sources": sources,
            "energy_data_source": None if energy == "unknown" else "osm",
            "source_raw": raw_source,
            "capacity_mw": capacity,
            "capacity_raw": raw_capacity if capacity is None and raw_capacity is not None else None,
            "capacity_source": None if capacity is None else "osm",
            "n_generators": self.n_generators,
            "geom_src": self.geometry.geom_type,
            "missing_capacity": capacity is None,
            "missing_energy": energy == "unknown",
        }

    def to_feature(self) -> dict:
        x, y = self.point.x, self.point.y
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(x, 6), round(y, 6)]},
            "properties": self.properties(),
        }


@dataclass
class BuildResult:
    facilities: list[Facility]
    log: list[dict]
    excluded_rooftop_solar: int
    generators_aggregated: int
    same_name_merged: int


def read_facilities(path: str | Path) -> list[Facility]:
    items = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            feature = json.loads(line)
            props = feature["properties"]
            kind = props["tags"].get("power")
            if kind not in ("plant", "generator"):
                continue
            items.append(Facility(props["osm_type"], props["osm_id"], kind, props["tags"], shape(feature["geometry"])))
    return items


def aggregate_generators(facilities: list[Facility]) -> tuple[list[Facility], list[dict]]:
    """Fold generators whose point lies inside a plant polygon into that plant."""
    plants = [f for f in facilities if f.kind == "plant" and f.geometry.geom_type in ("Polygon", "MultiPolygon")]
    tree = STRtree([p.geometry for p in plants])
    areas = [to_3826(p.geometry).area for p in plants]
    kept: list[Facility] = []
    log: list[dict] = []
    for f in facilities:
        if f.kind != "generator":
            kept.append(f)
            continue
        hits = [i for i in tree.query(f.point, predicate="within")]
        if not hits:
            kept.append(f)
            continue
        owner = plants[min(hits, key=lambda i: areas[i])]
        owner.n_generators += 1
        log.append(
            {"action": "generator_in_plant", "kept_osm_id": owner.ref, "dropped_osm_id": f.ref,
             "reason": "generator point inside plant polygon", "distance_m": None}
        )
    return kept, log


def exclude_rooftop(facilities: list[Facility], threshold_mw: float) -> tuple[list[Facility], list[dict]]:
    """Drop standalone rooftop generators and small solar generators."""
    kept, log = [], []
    for f in facilities:
        if f.kind == "generator":
            rooftop = tag_text(f.tags.get("generator:location")) == "roof"
            capacity = f.capacity_mw
            small_solar = f.energy[0] == "solar" and capacity is not None and capacity < threshold_mw
            if rooftop or small_solar:
                reason = "generator:location=roof" if rooftop else f"solar capacity {capacity} MW < {threshold_mw} MW"
                log.append({"action": "rooftop_solar_excluded", "kept_osm_id": None, "dropped_osm_id": f.ref,
                            "reason": reason, "distance_m": None})
                continue
        kept.append(f)
    return kept, log


def merge_same_name(facilities: list[Facility], distance_m: float) -> tuple[list[Facility], list[dict]]:
    """Drop node facilities that duplicate a nearby way/relation facility with the same name."""
    areas_by_name: dict[str, list[Facility]] = {}
    for f in facilities:
        if f.osm_type != "node" and f.name:
            areas_by_name.setdefault(f.name, []).append(f)
    projected = {id(f): to_3826(f.point) for f in facilities}
    kept, log = [], []
    for f in facilities:
        candidates = areas_by_name.get(f.name or "", []) if f.osm_type == "node" else []
        best = None
        for other in candidates:
            d = projected[id(f)].distance(projected[id(other)])
            if d < distance_m and (best is None or d < best[1]):
                best = (other, d)
        if best is None:
            kept.append(f)
            continue
        log.append({"action": "same_name_nearby", "kept_osm_id": best[0].ref, "dropped_osm_id": f.ref,
                    "reason": f"same name '{f.name}'", "distance_m": round(best[1], 1)})
    return kept, log


def build(facilities: list[Facility], rooftop_threshold_mw: float = 1.0, dedup_distance_m: float = 500.0) -> BuildResult:
    step1, log1 = aggregate_generators(facilities)
    step2, log2 = exclude_rooftop(step1, rooftop_threshold_mw)
    step3, log3 = merge_same_name(step2, dedup_distance_m)
    return BuildResult(step3, log1 + log2 + log3, len(log2), len(log1), len(log3))


def write_outputs(result: BuildResult, output: str | Path, dedup_log: str | Path, meta: str | Path | None) -> None:
    output, dedup_log = Path(output), Path(dedup_log)
    output.parent.mkdir(parents=True, exist_ok=True)
    collection = {"type": "FeatureCollection", "features": [f.to_feature() for f in result.facilities]}
    output.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    with dedup_log.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=DEDUP_LOG_HEADER)
        writer.writeheader()
        writer.writerows(result.log)
    if meta:
        Path(meta).write_text(
            json.dumps(
                {
                    "excluded_rooftop_solar": result.excluded_rooftop_solar,
                    "generators_aggregated": result.generators_aggregated,
                    "same_name_merged": result.same_name_merged,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dedup-log", required=True)
    parser.add_argument("--meta")
    parser.add_argument("--rooftop-threshold-mw", type=float, default=1.0)
    parser.add_argument("--dedup-distance-m", type=float, default=500.0)
    args = parser.parse_args(argv)

    result = build(read_facilities(args.input), args.rooftop_threshold_mw, args.dedup_distance_m)
    write_outputs(result, args.output, args.dedup_log, args.meta)
    print(
        f"Facilities: {len(result.facilities)} "
        f"(generators folded into plants: {result.generators_aggregated}, "
        f"rooftop/small solar excluded: {result.excluded_rooftop_solar}, "
        f"same-name merged: {result.same_name_merged})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
