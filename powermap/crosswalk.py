"""Link official plants to OSM facilities.

Implements the ``official-crosswalk`` spec: name normalization, crosswalk
candidates for human review, and loading of the reviewed ``crosswalk.csv``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_LEADING = ("台灣電力公司", "台電")
_TRAILING = ("發電廠", "發電站", "電廠", "分廠", "廠")
_SPACE_RE = re.compile(r"\s+")


def chinese_part(text: str) -> str:
    """Drop a trailing English name: cut at the first ``/`` after which only ASCII remains.

    ``中科E/S太陽光電發電站/Zhongke E/S Solar Power Station`` → ``中科E/S太陽光電發電站``.
    """
    for i, ch in enumerate(text):
        if ch == "/" and text[i + 1:].isascii() and not text[:i].isascii():
            return text[:i].strip()
    return text.strip()


def normalize_name(name: str | None) -> str:
    """Normalize a plant name for matching, e.g. ``台電大潭發電廠`` → ``大潭``."""
    if not name:
        return ""
    text = unicodedata.normalize("NFKC", name).replace("臺", "台")
    text = _SPACE_RE.sub("", chinese_part(text))
    for prefix in _LEADING:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    changed = True
    while changed:
        changed = False
        for suffix in _TRAILING:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)]
                changed = True
                break
    return text


# --- Crosswalk candidates -----------------------------------------------------------

CANDIDATE_HEADER = ("official_id", "official_name", "county", "official_capacity_mw", "osm_id", "osm_name",
                    "osm_kind", "osm_capacity_mw", "lon", "lat", "osm_url", "match_type")


def find_candidates(official_plants: list[dict], facilities: list[dict]) -> list[dict]:
    """Candidate pairs for human review; one ``none`` row for plants without candidates."""
    named = []
    for feature in facilities:
        props = feature["properties"]
        normalized = normalize_name(props.get("name"))
        if normalized:
            named.append((normalized, feature))
    rows: list[dict] = []
    for plant in official_plants:
        official = plant["name_normalized"]
        base = {"official_id": plant["official_id"], "official_name": plant["name"], "county": plant["county"] or "",
                "official_capacity_mw": plant["capacity_mw"]}
        found = []
        for normalized, feature in named:
            if normalized == official:
                match_type = "exact"
            elif min(len(normalized), len(official)) >= 2 and (normalized in official or official in normalized):
                match_type = "contains"
            else:
                continue
            props = feature["properties"]
            lon, lat = feature["geometry"]["coordinates"]
            found.append({**base, "osm_id": props["osm_id"], "osm_name": props["name"], "osm_kind": props["kind"],
                          "osm_capacity_mw": "" if props["capacity_mw"] is None else props["capacity_mw"],
                          "lon": lon, "lat": lat, "osm_url": props["osm_url"], "match_type": match_type})
        found.sort(key=lambda r: (r["match_type"] != "exact", r["osm_id"]))
        rows.extend(found or [{**base, **{k: "" for k in CANDIDATE_HEADER if k not in base}, "match_type": "none"}])
    return rows


# --- Crosswalk file ------------------------------------------------------------------

CROSSWALK_HEADER = ("official_id", "osm_ids", "relation", "note")
RELATIONS = ("same", "part", "none")


class CrosswalkError(Exception):
    """The crosswalk file is inconsistent; the pipeline must stop."""


@dataclass
class Link:
    official_id: str
    relation: str
    osm_ids: list[str]  # only ids present in the facility dataset, in file order


@dataclass
class Crosswalk:
    links: dict[str, Link] = field(default_factory=dict)  # by official_id
    osm_missing: list[str] = field(default_factory=list)  # official ids whose ids were all ignored
    warnings: list[str] = field(default_factory=list)
    ignored_ids: int = 0


def load_crosswalk(path: str | Path, official_ids: set[str], facility_ids: set[str]) -> Crosswalk:
    """Read and check ``crosswalk.csv``; a missing file means nothing is reviewed yet."""
    result = Crosswalk()
    path = Path(path)
    if not path.exists():
        result.warnings.append(f"{path} not found: every official plant is unreviewed")
        return result
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in CROSSWALK_HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise CrosswalkError(f"{path}: missing column(s): {', '.join(missing)}")
        rows = [(n, row) for n, row in enumerate(reader, start=2)]

    errors: list[str] = []
    by_official: dict[str, list[int]] = defaultdict(list)
    by_osm: dict[str, list[int]] = defaultdict(list)
    for line, row in rows:
        by_official[row["official_id"].strip()].append(line)
        for osm_id in _split_ids(row["osm_ids"]):
            by_osm[osm_id].append(line)
        if row["relation"].strip() not in RELATIONS:
            errors.append(f"line {line}: relation '{row['relation']}' is not one of {', '.join(RELATIONS)}")
    errors += [f"official_id {k} appears on lines {v}" for k, v in by_official.items() if len(v) > 1]
    errors += [f"OSM id {k} appears on lines {v}" for k, v in by_osm.items() if len(v) > 1]
    if errors:
        raise CrosswalkError("invalid crosswalk:\n  " + "\n  ".join(errors))

    for line, row in rows:
        official_id, relation = row["official_id"].strip(), row["relation"].strip()
        if official_id not in official_ids:
            result.warnings.append(f"line {line}: {official_id} is not in the official list; row ignored")
            continue
        ids = []
        for osm_id in _split_ids(row["osm_ids"]):
            if osm_id in facility_ids:
                ids.append(osm_id)
            else:
                result.ignored_ids += 1
                result.warnings.append(f"line {line}: {osm_id} is not in the facility dataset; ignored")
        if relation != "none" and not ids:
            result.osm_missing.append(official_id)
            continue
        result.links[official_id] = Link(official_id, relation, ids)
    return result


def _split_ids(value: str | None) -> list[str]:
    return [t.strip() for t in (value or "").split(";") if t.strip()]


# --- CLI -------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write crosswalk candidates for human review")
    parser.add_argument("--official", required=True, help="official_plants.json")
    parser.add_argument("--facilities", required=True, help="facilities GeoJSON")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    plants = json.loads(Path(args.official).read_text(encoding="utf-8"))["plants"]
    facilities = json.loads(Path(args.facilities).read_text(encoding="utf-8"))["features"]
    rows = find_candidates(plants, facilities)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CANDIDATE_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    best: dict[str, str] = {}
    for row in rows:
        current = best.get(row["official_id"])
        if current is None or RANK[row["match_type"]] < RANK[current]:
            best[row["official_id"]] = row["match_type"]
    counts = {t: sum(1 for v in best.values() if v == t) for t in RANK}
    print(f"Crosswalk candidates: {len(rows)} rows for {len(best)} official plants "
          f"(exact {counts['exact']}, contains {counts['contains']}, none {counts['none']}) -> {output}")
    return 0


RANK = {"exact": 0, "contains": 1, "none": 2}

if __name__ == "__main__":
    sys.exit(main())
