# osm-power-extraction Specification

## Purpose

Download the Geofabrik Taiwan OpenStreetMap snapshot and extract power-related features on the Taiwan main island and its nearby islets into a line-delimited GeoJSON file, with a summary that lets a person confirm feature counts, multi-source facilities, and exclusions before further processing.

## Requirements

### Requirement: Snapshot download

The system SHALL download the Taiwan snapshot from `https://download.geofabrik.de/asia/taiwan-latest.osm.pbf` to `data/raw/taiwan-latest.osm.pbf`. The system SHALL skip the download when that file already exists. The system SHALL exit with a non-zero status and SHALL NOT leave a partial file at the target path when the download fails.

#### Scenario: First run downloads the snapshot

- **WHEN** `data/raw/taiwan-latest.osm.pbf` does not exist and the download command runs
- **THEN** the file exists at that path after the command exits with status 0

#### Scenario: Existing snapshot is reused

- **WHEN** `data/raw/taiwan-latest.osm.pbf` already exists and `make data` runs
- **THEN** no network download is performed for the snapshot

#### Scenario: Failed download stops the pipeline

- **WHEN** the download fails
- **THEN** the command exits with a non-zero status and no file remains at `data/raw/taiwan-latest.osm.pbf`


<!-- @trace
source: build-power-data-pipeline
updated: 2026-11-12
code:
  - tests/osm_builder.py
  - scripts/download.sh
  - powermap/osm.py
  - tests/__init__.py
  - uv.lock
  - data/processed/.gitkeep
  - pyproject.toml
  - .python-version
  - Makefile
  - data/raw/.gitkeep
  - powermap/lines.py
  - README.md
  - powermap/extract.py
  - data/processed/plants.geojson
  - data/processed/dedup_log.csv
  - data/processed/stats.json
  - powermap/stats.py
  - powermap/parsers.py
  - powermap/geo.py
  - powermap/__init__.py
  - data/interim/.gitkeep
  - data/processed/lines.geojson
  - powermap/facilities.py
tests:
  - tests/test_extract.py
  - tests/test_facilities.py
  - tests/test_stats.py
  - tests/test_parsers.py
  - tests/test_download.py
  - tests/test_lines.py
-->

---
### Requirement: Snapshot timestamp recording

The system SHALL read the snapshot timestamp from the pbf header field `osmosis_replication_timestamp` and record it as an ISO 8601 UTC string. When the header lacks the field, the system SHALL record `null` and print a warning.

#### Scenario: Header contains a timestamp

- **WHEN** the pbf header has `osmosis_replication_timestamp=2026-11-02T21:21:00Z`
- **THEN** the extraction summary records snapshot `2026-11-02T21:21:00Z`

#### Scenario: Header lacks a timestamp

- **WHEN** the pbf header has no `osmosis_replication_timestamp`
- **THEN** the extraction summary records snapshot `null` and a warning is printed


<!-- @trace
source: build-power-data-pipeline
updated: 2026-11-12
code:
  - tests/osm_builder.py
  - scripts/download.sh
  - powermap/osm.py
  - tests/__init__.py
  - uv.lock
  - data/processed/.gitkeep
  - pyproject.toml
  - .python-version
  - Makefile
  - data/raw/.gitkeep
  - powermap/lines.py
  - README.md
  - powermap/extract.py
  - data/processed/plants.geojson
  - data/processed/dedup_log.csv
  - data/processed/stats.json
  - powermap/stats.py
  - powermap/parsers.py
  - powermap/geo.py
  - powermap/__init__.py
  - data/interim/.gitkeep
  - data/processed/lines.geojson
  - powermap/facilities.py
tests:
  - tests/test_extract.py
  - tests/test_facilities.py
  - tests/test_stats.py
  - tests/test_parsers.py
  - tests/test_download.py
  - tests/test_lines.py
-->

---
### Requirement: Power feature extraction

The system SHALL extract nodes, ways, and relations whose `power` tag is one of `plant`, `generator`, `substation`, `line`, `minor_line`, `cable` and that pass the main island scope filter into `data/interim/power.geojsonseq`, one GeoJSON Feature per line. Each Feature SHALL carry all original OSM tags plus `osm_type` (`node`, `way`, or `relation`) and the original numeric OSM id. For `plant`, `generator` and `substation`, a closed way or a multipolygon relation SHALL be emitted as a Polygon or MultiPolygon, and a node as a Point. For `line`, `minor_line`, and `cable`, ways SHALL be emitted as LineString. Features with other `power` values, including `tower`, SHALL NOT be emitted. Adding `substation` SHALL NOT change which `plant`, `generator`, `line`, `minor_line` or `cable` Features are emitted, and SHALL NOT change the count of multi-source facilities.

#### Scenario: Closed plant way becomes a polygon

- **WHEN** a closed way is tagged `power=plant`
- **THEN** its Feature in `power.geojsonseq` has a Polygon geometry, `osm_type` `way`, and the way's original id

#### Scenario: Closed cable way stays a line

- **WHEN** a closed way is tagged `power=cable`
- **THEN** its Feature in `power.geojsonseq` has a LineString geometry

#### Scenario: Substation is extracted

- **WHEN** a closed way is tagged `power=substation` and a node is tagged `power=substation`
- **THEN** `power.geojsonseq` has a Polygon Feature for the way and a Point Feature for the node

#### Scenario: Tower is excluded

- **WHEN** a node is tagged `power=tower`
- **THEN** no Feature for it appears in `power.geojsonseq`

#### Scenario: Substation outside the main island is excluded

- **WHEN** a substation lies entirely within the Kinmen box
- **THEN** it is not emitted and the summary counts it under `kinmen` and under `power` value `substation`


<!-- @trace
source: add-substations
updated: 2026-11-13
code:
  - Makefile
  - README.md
  - powermap/stats.py
  - data/processed/stats.json
  - powermap/substations.py
  - powermap/osm.py
  - .github/workflows/pages.yml
  - web/app.js
  - web/index.html
  - web/lib.js
  - powermap/extract.py
  - web/style.css
  - data/processed/substations.geojson
tests:
  - web/tests/lib.test.js
  - tests/test_substations.py
  - tests/test_stats.py
  - tests/test_extract.py
-->

---
### Requirement: Main island scope filter

The system SHALL keep a feature only when its geometry intersects the main island bounding box, which defaults to longitude 119.3–122.2 and latitude 21.8–25.4 and is configurable with `--main-bbox`, and its geometry is not entirely within the Penghu box (lon 119.3–119.75, lat 23.1–23.8). A kept feature SHALL be emitted with its full geometry and SHALL NOT be clipped. Each excluded feature SHALL be counted under exactly one region, checked in this order: `penghu` when its geometry is entirely within the Penghu box, `kinmen` when it intersects lon 118.1–118.5, lat 24.3–24.6, `matsu` when it intersects lon 119.9–120.6, lat 25.9–26.4, otherwise `other`.

#### Scenario: Apply the main island filter

- **WHEN** features are filtered with the default bounding boxes
- **THEN** each is kept or excluded as listed

##### Example: scope decisions

| Feature location | Result | Region counted |
| ---------------- | ------ | -------------- |
| Point at lon 121.0, lat 24.0 (Taiwan main island) | kept | — |
| Point at lon 121.5, lat 22.05 (Orchid Island) | kept | — |
| Point at lon 118.35, lat 24.45 (Kinmen) | excluded | `kinmen` |
| Point at lon 119.95, lat 26.15 (Matsu) | excluded | `matsu` |
| Point at lon 119.6, lat 23.57 (Penghu) | excluded | `penghu` |
| Point at lon 116.7, lat 20.7 (Pratas) | excluded | `other` |
| Point at lon 119.85, lat 24.1 (Changhua offshore wind) | kept | — |
| Point at lon 120.0, lat 25.8 (Fujian offshore wind) | excluded | `other` |
| Line from lon 119.6, lat 23.5 to lon 120.15, lat 23.6 (Taiwan–Penghu cable) | kept, geometry unclipped | — |


<!-- @trace
source: build-power-data-pipeline
updated: 2026-11-12
code:
  - tests/osm_builder.py
  - scripts/download.sh
  - powermap/osm.py
  - tests/__init__.py
  - uv.lock
  - data/processed/.gitkeep
  - pyproject.toml
  - .python-version
  - Makefile
  - data/raw/.gitkeep
  - powermap/lines.py
  - README.md
  - powermap/extract.py
  - data/processed/plants.geojson
  - data/processed/dedup_log.csv
  - data/processed/stats.json
  - powermap/stats.py
  - powermap/parsers.py
  - powermap/geo.py
  - powermap/__init__.py
  - data/interim/.gitkeep
  - data/processed/lines.geojson
  - powermap/facilities.py
tests:
  - tests/test_extract.py
  - tests/test_facilities.py
  - tests/test_stats.py
  - tests/test_parsers.py
  - tests/test_download.py
  - tests/test_lines.py
-->

---
### Requirement: Extraction summary

After extraction the system SHALL print, and write to `data/interim/extract_summary.json`, the snapshot timestamp; the count of kept Features for each `power` value broken down by geometry type; the count of matching relations that produced no geometry; the count of kept `plant` and `generator` Features whose energy classifies as `mixed`; the count of excluded Features per region (`kinmen`, `matsu`, `penghu`, `other`) and per `power` value; the OSM ids of Features excluded under `other`; and the count of Features skipped because of invalid geometry.

#### Scenario: Summary lists counts by power value and geometry

- **WHEN** extraction finishes
- **THEN** `extract_summary.json` contains a count for every combination of `power` value and geometry type that occurred among kept Features, and the same numbers are printed to the terminal

#### Scenario: Summary reports multi-source facilities

- **WHEN** the snapshot contains 3 kept plants tagged `plant:source=coal;gas` and 1 kept plant tagged `plant:source=solar`
- **THEN** the summary reports 3 multi-source facilities

#### Scenario: Summary reports exclusions by region

- **WHEN** 40 features lie in Kinmen and 2 features lie in Pratas
- **THEN** the summary reports `kinmen` 40 and `other` 2, and lists the OSM ids of the 2 `other` features

<!-- @trace
source: build-power-data-pipeline
updated: 2026-11-12
code:
  - tests/osm_builder.py
  - scripts/download.sh
  - powermap/osm.py
  - tests/__init__.py
  - uv.lock
  - data/processed/.gitkeep
  - pyproject.toml
  - .python-version
  - Makefile
  - data/raw/.gitkeep
  - powermap/lines.py
  - README.md
  - powermap/extract.py
  - data/processed/plants.geojson
  - data/processed/dedup_log.csv
  - data/processed/stats.json
  - powermap/stats.py
  - powermap/parsers.py
  - powermap/geo.py
  - powermap/__init__.py
  - data/interim/.gitkeep
  - data/processed/lines.geojson
  - powermap/facilities.py
tests:
  - tests/test_extract.py
  - tests/test_facilities.py
  - tests/test_stats.py
  - tests/test_parsers.py
  - tests/test_download.py
  - tests/test_lines.py
-->