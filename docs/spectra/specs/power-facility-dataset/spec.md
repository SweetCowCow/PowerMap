# power-facility-dataset Specification

## Purpose

Turn OSM `power=plant` and `power=generator` features into a deduplicated point dataset of power facilities with normalized energy categories, capacity, and value provenance, keeping missing values explicit and every merge traceable.

## Requirements

### Requirement: Energy classification

The system SHALL derive `energy` and `energy_sources` from `plant:source` for plants and `generator:source` for generators. The value SHALL be lowercased, split on `;`, trimmed, and empty tokens discarded. Each remaining token SHALL be normalized to a category: `solar`, `wind`, `hydro`, `gas`, `coal`, `nuclear`, `geothermal` map to the category of the same name, and every other token maps to `other`. `energy_sources` SHALL list the distinct normalized categories in order of first appearance. When `energy_sources` has exactly one category, `energy` SHALL be that category; when it has two or more, `energy` SHALL be `mixed`; when the tag is missing, empty, or contains only empty tokens, `energy` SHALL be `unknown` and `energy_sources` SHALL be an empty array. The system SHALL NOT choose a primary source for a `mixed` facility. The original tag string SHALL be kept in `source_raw` (`null` when the tag is absent).

#### Scenario: Classify source tag values

- **WHEN** the source tag is classified
- **THEN** `energy` and `energy_sources` match the expected values

##### Example: energy categories

| source tag | energy | energy_sources | Notes |
| ---------- | ------ | -------------- | ----- |
| `solar` | `solar` | `["solar"]` | single source |
| `Wind` | `wind` | `["wind"]` | case-insensitive |
| `coal;gas` | `mixed` | `["coal","gas"]` | no primary source chosen |
| `gas;coal` | `mixed` | `["gas","coal"]` | order of appearance kept |
| `solar;solar` | `solar` | `["solar"]` | duplicates collapse |
| ` ;nuclear` | `nuclear` | `["nuclear"]` | empty token discarded |
| `diesel` | `other` | `["other"]` | listed other fuel |
| `oil;diesel` | `other` | `["other"]` | both normalize to other |
| `coal;biomass` | `mixed` | `["coal","other"]` | recognized plus other |
| `battery` | `other` | `["other"]` | unrecognized single source |
| (absent) | `unknown` | `[]` | no tag |
| `""` | `unknown` | `[]` | empty tag |


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
### Requirement: Facility value provenance

Each facility SHALL carry `capacity_source` and `energy_data_source`. `capacity_source` SHALL be `osm` when `capacity_mw` is a number and `null` when `capacity_mw` is `null`. `energy_data_source` SHALL be `osm` when `energy` is not `unknown` and `null` when `energy` is `unknown`.

#### Scenario: Provenance follows the value

- **WHEN** a plant has `plant:output:electricity=550 MW` and no source tag
- **THEN** it has `capacity_source` `osm` and `energy_data_source` `null`


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
### Requirement: Capacity parsing

The system SHALL parse `plant:output:electricity` or `generator:output:electricity` into `capacity_mw` (a number in megawatts). Units `W`, `kW`, `kWp`, `MW`, `MWp`, `GW` SHALL be accepted case-insensitively with optional whitespace between number and unit. A number without a unit SHALL be interpreted as MW. The value `yes`, any other unparseable string, a comma-decimal number, or a negative number SHALL produce `capacity_mw` `null`, and the original string SHALL be stored in `capacity_raw`. When parsing succeeds or the tag is absent, `capacity_raw` SHALL be `null`. `missing_capacity` SHALL be `true` exactly when `capacity_mw` is `null`.

#### Scenario: Parse capacity strings

- **WHEN** a capacity tag is parsed
- **THEN** `capacity_mw` and `capacity_raw` match the expected values

##### Example: capacity parsing

| tag value | capacity_mw | capacity_raw |
| --------- | ----------- | ------------ |
| `550 MW` | 550 | null |
| `1.2 GW` | 1200 | null |
| `499 kW` | 0.499 | null |
| `4500 kWp` | 4.5 | null |
| `2MWp` | 2 | null |
| `500` | 500 | null |
| `yes` | null | `yes` |
| `1,5 MW` | null | `1,5 MW` |
| `about 3 MW` | null | `about 3 MW` |
| (absent) | null | null |


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
### Requirement: Facility point geometry

Each output facility SHALL be a Point in EPSG:4326. Polygon and line source geometries SHALL be converted with `representative_point()`, which lies inside the source geometry. The source geometry type SHALL be stored in `geom_src` (`Point`, `LineString`, `Polygon`, or `MultiPolygon`).

#### Scenario: Polygon plant becomes an interior point

- **WHEN** a plant has a concave Polygon geometry
- **THEN** its output Point lies inside that polygon and `geom_src` is `Polygon`


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
### Requirement: Generators inside plants are aggregated

A `generator` whose representative point lies inside a `plant` Polygon or MultiPolygon SHALL NOT appear as a separate facility. When the point lies inside several plant polygons, the generator SHALL be assigned to the plant with the smallest area. The containing plant's `n_generators` SHALL equal the number of such generators. Plants with no contained generators, and plants whose geometry is a Point, SHALL have `n_generators` 0. Each aggregation SHALL be written to `data/processed/dedup_log.csv` with action `generator_in_plant`.

#### Scenario: Wind turbines inside a wind farm polygon

- **WHEN** 12 generators lie inside one plant polygon
- **THEN** that plant has `n_generators` 12, none of the 12 generators appears in `plants.geojson`, and `dedup_log.csv` has 12 rows with action `generator_in_plant`


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
### Requirement: Standalone rooftop and small solar exclusion

A generator not aggregated into a plant SHALL be excluded from the output when it has `generator:location=roof`, or when its energy is `solar` and its `capacity_mw` is a number below the rooftop threshold (default 1 MW, configurable with `--rooftop-threshold-mw`). A solar generator with `capacity_mw` `null` and no `generator:location=roof` SHALL be kept. The number of excluded generators SHALL be reported as `excluded_rooftop_solar` in statistics.

#### Scenario: Apply rooftop exclusion

- **WHEN** standalone generators are filtered with the default threshold
- **THEN** each is kept or excluded as listed

##### Example: rooftop rule with 1 MW threshold

| generator:location | energy | capacity_mw | Result |
| ------------------ | ------ | ----------- | ------ |
| `roof` | `solar` | 5 | excluded |
| (absent) | `solar` | 0.3 | excluded |
| (absent) | `solar` | 1 | kept |
| (absent) | `solar` | null | kept |
| (absent) | `wind` | 0.5 | kept |


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
### Requirement: Same-name node and area duplicates are merged

When a facility from a node and a facility from a way or relation have identical `name` after trimming whitespace, and their distance computed in EPSG:3826 is below the dedup distance (default 500 m, configurable with `--dedup-distance-m`), the system SHALL keep the way or relation facility and drop the node facility. Facilities without a `name` SHALL NOT be merged by this rule. Each merge SHALL be written to `dedup_log.csv` with action `same_name_nearby` and the measured distance in meters.

#### Scenario: Node duplicate of a plant area is dropped

- **WHEN** node `n1` and way `w2` are both named `大潭發電廠` and are 120 m apart
- **THEN** only `w2` appears in `plants.geojson` and `dedup_log.csv` has a row `same_name_nearby,w2,n1,…,120`

#### Scenario: Same name far apart is kept

- **WHEN** a node and a way share a name but are 800 m apart
- **THEN** both appear in `plants.geojson`


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
### Requirement: Facility dataset output

The system SHALL write `data/processed/plants.geojson` as a GeoJSON FeatureCollection of Points in EPSG:4326. Each Feature's properties SHALL contain exactly: `osm_id` (`n`, `w`, or `r` followed by the numeric id), `osm_url` (`https://www.openstreetmap.org/{node|way|relation}/{id}`), `kind` (`plant` or `generator`), `name` (the `name` tag; falls back to `name:zh`, then `null` when both are absent), `operator`, `energy`, `energy_sources`, `energy_data_source`, `source_raw`, `capacity_mw`, `capacity_raw`, `capacity_source`, `n_generators`, `geom_src`, `missing_capacity`, `missing_energy`. `missing_energy` SHALL be `true` exactly when `energy` is `unknown`. Absent values SHALL be JSON `null`, never `0` or an empty string, except `n_generators`, which is an integer count, and `energy_sources`, which is an array that is empty when no source is known. The system SHALL write `data/processed/dedup_log.csv` with header `action,kept_osm_id,dropped_osm_id,reason,distance_m`.

#### Scenario: Missing values stay null

- **WHEN** a plant has no `operator` tag and no output tag
- **THEN** its properties have `operator` `null`, `capacity_mw` `null`, `capacity_raw` `null`, and `missing_capacity` `true`

#### Scenario: OSM identifiers are traceable

- **WHEN** a facility comes from way 123456
- **THEN** its `osm_id` is `w123456` and its `osm_url` is `https://www.openstreetmap.org/way/123456`

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