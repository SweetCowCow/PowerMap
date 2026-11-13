"""Compare the current pipeline outputs with a git commit and list what needs human review.

Implements the ``data-refresh`` spec ("Change report"). Run after ``make data`` (``make refresh``
does it for you); the report goes to the terminal and to ``--output``.

Usage::

    python -m powermap.refresh_report --base-ref HEAD --output data/interim/refresh_report.md
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from powermap.official_points import LocationError, linked_official_ids, load_locations
from powermap.official_status import StatusError, load_status

STATS = "data/processed/stats.json"
UNMATCHED = "data/processed/unmatched.csv"
DIFF = "data/processed/official_diff.csv"
ENRICH_META = "data/interim/enrich_meta.json"
OFFICIAL = "data/interim/official_plants.json"
CROSSWALK = "data/official/crosswalk.csv"
LOCATIONS = "data/official/locations.csv"
STATUS_TABLE = "data/official/status.csv"
STALE_AFTER = timedelta(days=365)

#: (label, path into stats.json) for the count table, in report order.
COUNTS = (
    ("設施", ("facilities",)),
    ("電力線", ("lines",)),
    ("變電所", ("substations",)),
    ("對到 OSM 的官方電廠", ("official", "linked")),
    ("OSM 沒有的官方電廠（no_osm）", ("official", "unmatched", "no_osm")),
    ("有估計位置的官方電廠", ("official", "located")),
    ("缺容量的設施", ("facilities_missing_capacity",)),
    ("缺電壓的線段", ("lines_missing_voltage",)),
)


class ReportError(Exception):
    """The base version cannot be read (for example, an unknown git ref)."""


def _get(data: dict, path: tuple[str, ...]):
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def _count_text(before, after) -> str:
    b, a = before or 0, after or 0
    return f"{b:,} → {a:,} ({a - b:+,})"


def _csv_rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿")))) if text.strip() else []


def build_report(base: dict, current: dict, today: date) -> tuple[str, int]:
    """Markdown report and the number of review items.

    ``base`` and ``current`` hold ``stats`` (dict), ``unmatched`` and ``diff`` (CSV rows).
    ``current`` also holds ``enrich_warnings``, ``location_warnings``, ``status_warnings``
    (strings) and ``status_rows`` (rows of status.csv).
    """
    b_stats, c_stats = base.get("stats") or {}, current.get("stats") or {}
    lines = ["# 資料更新報告", "", f"產生日期：{today.isoformat()}", "", "## 資料來源", "",
             "| 項目 | 上次 | 這次 |", "| --- | --- | --- |",
             f"| OSM 快照 | {b_stats.get('snapshot') or '—'} | {c_stats.get('snapshot') or '—'} |",
             f"| 台電資料目錄 | {_get(b_stats, ('official', 'source_dir')) or '—'} | "
             f"{_get(c_stats, ('official', 'source_dir')) or '—'} |",
             "", "## 數量變化", "", "| 項目 | 上次 → 這次（差） |", "| --- | --- |"]
    for label, path in COUNTS:
        lines.append(f"| {label} | {_count_text(_get(b_stats, path), _get(c_stats, path))} |")

    items: list[str] = []
    for row in current.get("unmatched", []):
        if row.get("reason") == "unreviewed":
            items.append(f"- `{row['official_id']}` {row.get('name', '')}：尚未審閱。執行 `make crosswalk-candidates`，"
                         "在 `data/official/crosswalk.csv` 加一列")
        elif row.get("reason") == "osm_missing":
            items.append(f"- `{row['official_id']}` {row.get('name', '')}：對照表的 OSM id 已失效，"
                         "檢查 `data/official/crosswalk.csv` 該列")
    items += [f"- 對照表：{w}" for w in current.get("enrich_warnings", [])]
    items += [f"- 位置表 `data/official/locations.csv`：{w}" for w in current.get("location_warnings", [])]
    items += [f"- 狀態表 `data/official/status.csv`：{w}" for w in current.get("status_warnings", [])]
    for row in current.get("status_rows", []):
        try:
            checked = date.fromisoformat(row["checked_at"])
        except (KeyError, ValueError):
            continue
        if today - checked > STALE_AFTER:
            items.append(f"- 狀態表 `{row['official_id']}`：查證日期 {row['checked_at']} 已超過一年，請重新確認")
    base_diff_ids = {r.get("official_id") for r in base.get("diff", [])}
    for row in current.get("diff", []):
        if row.get("official_id") not in base_diff_ids:
            items.append(f"- 新的容量差距：`{row['official_id']}`（OSM {row.get('osm_capacity_mw')} MW，"
                         f"官方 {row.get('official_capacity_mw')} MW）")

    lines += ["", "## 待處理", ""]
    lines += items or ["（沒有）"]
    lines += ["", f"待處理 {len(items)} 項", ""]
    return "\n".join(lines), len(items)


# --- Inputs --------------------------------------------------------------------------


def git_show(ref: str, path: str, cwd: str | Path = ".") -> str:
    """File content at ``ref``; empty string when the file does not exist there."""
    check = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                           cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if check.returncode != 0:
        raise ReportError(f"git ref '{ref}' cannot be read (not a commit, or not a git repository)")
    shown = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8")
    return shown.stdout if shown.returncode == 0 else ""


def _read(path: str | Path) -> str:
    path = Path(path)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_base(ref: str, root: str | Path = ".") -> dict:
    stats_text = git_show(ref, STATS, root)
    return {"stats": json.loads(stats_text) if stats_text.strip() else {},
            "unmatched": _csv_rows(git_show(ref, UNMATCHED, root)),
            "diff": _csv_rows(git_show(ref, DIFF, root))}


def load_current(root: str | Path = ".") -> dict:
    root = Path(root)
    stats_text, meta_text, official_text = _read(root / STATS), _read(root / ENRICH_META), _read(root / OFFICIAL)
    official_ids = {p["official_id"] for p in json.loads(official_text)["plants"]} if official_text.strip() else set()
    current = {"stats": json.loads(stats_text) if stats_text.strip() else {},
               "unmatched": _csv_rows(_read(root / UNMATCHED)),
               "diff": _csv_rows(_read(root / DIFF)),
               "enrich_warnings": json.loads(meta_text).get("warnings", []) if meta_text.strip() else [],
               "location_warnings": [], "status_warnings": [], "status_rows": []}
    try:
        current["location_warnings"] = load_locations(root / LOCATIONS, official_ids,
                                                      linked_official_ids(root / CROSSWALK)).warnings
    except LocationError as exc:
        current["location_warnings"] = [str(exc)]
    try:
        table = load_status(root / STATUS_TABLE, official_ids)
        current["status_warnings"], current["status_rows"] = table.warnings, table.rows
    except StatusError as exc:
        current["status_warnings"] = [str(exc)]
    return current


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    args = parser.parse_args(argv)

    try:
        base = load_base(args.base_ref, args.root)
    except ReportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    report, _ = build_report(base, load_current(args.root), date.today())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(report)
    print(f"(saved to {output})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
