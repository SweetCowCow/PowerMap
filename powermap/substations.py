"""Build the substation point dataset from extracted ``power=substation`` features.

Implements the ``substation-dataset`` spec: one point per OSM object (no deduplication),
areas converted with ``representative_point()``, voltage parsed and classified like lines.

Usage::

    python -m powermap.substations --input data/interim/power.geojsonseq \
        --output data/processed/substations.geojson
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import shape

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


def build_substations(features: list[dict]) -> list[dict]:
    """Return Point features for every ``power=substation`` feature, sorted by OSM id."""
    selected = [f for f in features if f["properties"]["tags"].get("power") == "substation"]
    selected.sort(key=lambda f: (_TYPE_ORDER[f["properties"]["osm_type"]], f["properties"]["osm_id"]))
    out = []
    for feature in selected:
        props = feature["properties"]
        geom = shape(feature["geometry"])
        point = geom if geom.geom_type == "Point" else geom.representative_point()
        out.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(point.x, DECIMALS), round(point.y, DECIMALS)]},
                "properties": substation_properties(props["osm_type"], props["osm_id"], props["tags"], geom.geom_type),
            }
        )
    return out


def read_features(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    features = build_substations(read_features(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    missing = sum(f["properties"]["missing_voltage"] for f in features)
    print(f"Substations: {len(features)} ({missing} without voltage)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
