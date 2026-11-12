# power-line-dataset Specification

## Purpose

Turn OSM `power=line`, `power=minor_line`, and `power=cable` ways into a lightweight line dataset with parsed maximum voltage and a voltage class, keeping one feature per OSM way and never inventing connections.

## Requirements

### Requirement: Voltage parsing

The system SHALL parse the `voltage` tag (in volts) into `voltage_max_kv`: split on `;`, trim tokens, keep tokens that are plain non-negative numbers, take the maximum, and divide by 1000. When no token is numeric or the tag is absent, `voltage_max_kv` SHALL be `null`. The original tag string SHALL be stored in `voltage_raw` (`null` when absent). `missing_voltage` SHALL be `true` exactly when `voltage_max_kv` is `null`.

#### Scenario: Parse voltage strings

- **WHEN** a voltage tag is parsed
- **THEN** `voltage_max_kv` matches the expected value

##### Example: voltage parsing

| voltage tag | voltage_max_kv | Notes |
| ----------- | -------------- | ----- |
| `345000` | 345 | single value |
| `345000;161000` | 345 | maximum wins |
| `161000;69000;11400` | 161 | three values |
| `11400` | 11.4 | below 69 kV |
| `161000;unknown` | 161 | non-numeric token ignored |
| `high` | null | no numeric token |
| (absent) | null | no tag |


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
### Requirement: Voltage classification

The system SHALL assign `voltage_class` from `voltage_max_kv`: `ehv` for ≥ 345, `hv` for ≥ 161 and < 345, `mv` for ≥ 69 and < 161, `lv` for < 69, and `missing` for `null`.

#### Scenario: Classify voltage boundaries

- **WHEN** a voltage value is classified
- **THEN** the class matches the boundary table

##### Example: class boundaries

| voltage_max_kv | voltage_class |
| -------------- | ------------- |
| 345 | `ehv` |
| 344.9 | `hv` |
| 161 | `hv` |
| 160.9 | `mv` |
| 69 | `mv` |
| 68.9 | `lv` |
| 11.4 | `lv` |
| null | `missing` |


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
### Requirement: Line value provenance

Each line SHALL carry `voltage_source`, which SHALL be `osm` when `voltage_max_kv` is a number and `null` when `voltage_max_kv` is `null`.

#### Scenario: Provenance follows the voltage value

- **WHEN** one line has `voltage=161000` and another has no `voltage` tag
- **THEN** the first has `voltage_source` `osm` and the second has `voltage_source` `null`


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
### Requirement: One feature per OSM way without merging

The system SHALL output exactly one LineString feature per extracted `line`, `minor_line`, or `cable` way that has a LineString geometry. The system SHALL NOT merge, connect, extend, or add line segments.

#### Scenario: Adjacent ways stay separate

- **WHEN** two `power=line` ways share an endpoint
- **THEN** `lines.geojson` contains two separate features with their own `osm_id`


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
### Requirement: Line geometry simplification

The system SHALL simplify each line in EPSG:3826 with a tolerance of 10 m while preserving topology, transform the result to EPSG:4326, and round coordinates to 5 decimal places. A line whose simplified geometry is empty or invalid SHALL be skipped and counted in a printed warning.

#### Scenario: Coordinates are rounded

- **WHEN** `lines.geojson` is written
- **THEN** no coordinate in it has more than 5 decimal places


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
### Requirement: Line dataset output

The system SHALL write `data/processed/lines.geojson` as a GeoJSON FeatureCollection of LineStrings in EPSG:4326. Each Feature's properties SHALL contain exactly: `osm_id`, `osm_url`, `kind` (`line`, `minor_line`, or `cable`), `voltage_max_kv`, `voltage_raw`, `voltage_class`, `voltage_source`, `missing_voltage`, `location` (the OSM `location` tag, `null` when absent). Absent values SHALL be JSON `null`, never `0` or an empty string.

#### Scenario: Line without voltage

- **WHEN** a `power=minor_line` way has no `voltage` tag
- **THEN** its properties have `voltage_max_kv` `null`, `voltage_raw` `null`, `voltage_class` `missing`, `voltage_source` `null`, and `missing_voltage` `true`

#### Scenario: Submarine cable keeps its location

- **WHEN** a `power=cable` way has `location=underwater`
- **THEN** its properties have `kind` `cable` and `location` `underwater`

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