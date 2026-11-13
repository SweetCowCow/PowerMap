"""Publish the reviewed operating status table of official plants as a lookup file.

Implements the ``official-status`` spec. ``data/official/status.csv`` is maintained by hand
from public sources (Taipower, the nuclear safety commission, news reports); the official
open data does not say which units are retired.

Usage::

    python -m powermap.official_status --official data/interim/official_plants.json \
        --status data/official/status.csv --output data/processed/official_status.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATUS_HEADER = ("official_id", "status", "since", "units", "source", "checked_at", "note")
STATUSES = ("retired", "mothballed", "partially_retired")
OUTPUT_KEYS = ("status", "since", "units", "source", "checked_at", "note")
_SINCE_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")
_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


class StatusError(Exception):
    """The status table has invalid rows; the pipeline must stop."""


@dataclass
class StatusTable:
    rows: list[dict] = field(default_factory=list)  # valid rows, cells stripped
    warnings: list[str] = field(default_factory=list)


def _row_problems(row: dict) -> list[str]:
    problems = []
    if row["status"] not in STATUSES:
        problems.append(f"status '{row['status']}' is not one of {', '.join(STATUSES)}")
    if row["since"] and not _SINCE_RE.match(row["since"]):
        problems.append(f"since '{row['since']}' is not YYYY, YYYY-MM or YYYY-MM-DD")
    if not row["source"].startswith(("http://", "https://")):
        problems.append(f"source '{row['source']}' is not an http(s) URL")
    if not _DATE_RE.match(row["checked_at"]):
        problems.append(f"checked_at '{row['checked_at']}' is not YYYY-MM-DD")
    return problems


def load_status(path: str | Path, official_ids: set[str]) -> StatusTable:
    """Read and check ``status.csv``; a missing file is an empty table."""
    result = StatusTable()
    path = Path(path)
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in STATUS_HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise StatusError(f"{path}: missing column(s): {', '.join(missing)}")
        rows = [(line, {c: (row.get(c) or "").strip() for c in STATUS_HEADER})
                for line, row in enumerate(reader, start=2)]

    text = {line: ",".join(row[c] for c in STATUS_HEADER) for line, row in rows}
    errors: list[str] = []
    lines_by_id: dict[str, list[int]] = {}
    for line, row in rows:
        lines_by_id.setdefault(row["official_id"], []).append(line)
    for official_id, lines in lines_by_id.items():
        if len(lines) > 1:
            errors.append(f"official_id {official_id} appears on lines {lines}: "
                          + " | ".join(f"line {n}: {text[n]}" for n in lines))
    for line, row in rows:
        problems = _row_problems(row)
        if problems:
            errors.append(f"line {line}: {'; '.join(problems)}: {text[line]}")
    if errors:
        raise StatusError(f"invalid status rows in {path}:\n  " + "\n  ".join(errors))

    for line, row in rows:
        if row["official_id"] in official_ids:
            result.rows.append(row)
        else:
            result.warnings.append(f"line {line}: {row['official_id']} is not in the official list; row ignored")
    return result


def build(table: StatusTable) -> dict:
    """``{official_id: {status, since, units, source, checked_at, note}}`` with sorted keys."""
    return {row["official_id"]: {key: row[key] or None for key in OUTPUT_KEYS}
            for row in sorted(table.rows, key=lambda r: r["official_id"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ("official", "status", "output"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)

    plants = json.loads(Path(args.official).read_text(encoding="utf-8"))["plants"]
    try:
        table = load_status(args.status, {p["official_id"] for p in plants})
    except StatusError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for warning in table.warnings:
        print(f"warning: {warning}", file=sys.stderr)

    status = build(table)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Official status: {len(status)} plants (ignored rows: {len(table.warnings)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
