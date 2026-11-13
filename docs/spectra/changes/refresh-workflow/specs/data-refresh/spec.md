## Purpose

Refresh the OSM snapshot and the official open data with one command and report, against the last commit, what changed and which hand-maintained tables need review, so periodic updates are repeatable and nothing stale goes unnoticed.

## ADDED Requirements

### Requirement: Refresh command

The system SHALL provide `make refresh`, which downloads the OSM snapshot to a temporary file and replaces `data/raw/taiwan-latest.osm.pbf` only after the download succeeds, downloads the official datasets reusing today's snapshot directory when it already exists, runs `make data`, and then writes the change report. When any step fails, `make refresh` SHALL stop and exit non-zero, and a failed OSM download SHALL leave the previous snapshot in place.

#### Scenario: OSM download fails

- **WHEN** the OSM download fails during `make refresh`
- **THEN** `make refresh` exits non-zero and `data/raw/taiwan-latest.osm.pbf` is unchanged

### Requirement: Change report

The system SHALL compare the current outputs with the versions in a git ref (default `HEAD`) and write a Markdown report to `data/interim/refresh_report.md` and the terminal with, in order: data sources (OSM snapshot time and official snapshot directory, before and after); count changes (facilities, lines, substations, linked official plants, `no_osm`, located official plants, facilities missing capacity, lines missing voltage) as before, after and difference; a review list; and a final line `待處理 N 項`. The review list SHALL contain official plants with reason `unreviewed` or `osm_missing` in `unmatched.csv`, crosswalk warnings from `enrich_meta.json`, ignored rows of `locations.csv`, ignored rows of `status.csv`, status rows whose `checked_at` is more than 365 days before the report date, and rows of `official_diff.csv` whose `official_id` is not in the base version. A file missing in the base ref SHALL be treated as empty. The report command SHALL exit 0 when it can read all inputs, even with review items, and non-zero when the git ref cannot be read.

#### Scenario: Report contents

##### Example: review items

| Situation | Report shows |
| --- | --- |
| `unmatched.csv` has `ipp:新電廠` with reason `unreviewed` | `ipp:新電廠` under review items with the hint to run `make crosswalk-candidates` |
| facilities 1,570 at base, 1,575 now | facilities row `1,570 → 1,575 (+5)` |
| `status.csv` row checked on 2025-11-01, report date 2026-11-13 | that row listed as older than 365 days |
| nothing to review | `待處理 0 項` |

#### Scenario: New output file

- **WHEN** `official_diff.csv` does not exist in the base ref
- **THEN** every current row is listed as a new capacity discrepancy and the report still succeeds
