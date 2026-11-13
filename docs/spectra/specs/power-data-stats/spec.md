# power-data-stats Specification

## Purpose

Summarize the facility and line datasets into a single `stats.json` that records the snapshot time and the counts the web map and README rely on, including how much data is missing.

## Requirements

### Requirement: Statistics file

The system SHALL write `data/processed/stats.json` containing: `snapshot` (from the extraction summary, `null` when unknown), `built_at` (ISO 8601 UTC time of the stats run), `facilities` (feature count of `plants.geojson`), `lines` (feature count of `lines.geojson`), `lines_missing_voltage`, `facilities_missing_capacity`, `by_energy` (an object with all ten energy categories as keys: `solar`, `wind`, `hydro`, `gas`, `coal`, `nuclear`, `geothermal`, `other`, `mixed`, `unknown`), `by_energy_source` (an object with the eight source categories `solar`, `wind`, `hydro`, `gas`, `coal`, `nuclear`, `geothermal`, `other` as keys, counting each facility once for every category in its `energy_sources`), `by_voltage_class` (an object with all five voltage classes as keys), `excluded_rooftop_solar`, `excluded_outside_main_island` (an object with keys `kinmen`, `matsu`, `penghu`, `other`, copied from the extraction summary, counting raw OSM features), and `official` (an object with `source_dir`, `plants` (count in `official_plants.json`), `excluded_outside_main_island`, `linked` (official plants with a `same` or `part` link that still has at least one valid OSM id), `facilities_with_official_id`, `capacity_filled` (facilities with `capacity_source` `taipower`), `merged` (rows with action `official_same_plant` in `dedup_log.csv`), `capacity_discrepancies` (rows in `official_diff.csv`), and `unmatched` (an object with keys `no_osm`, `unreviewed`, `osm_missing`)). Categories with no features SHALL appear with value 0. Every count SHALL be computed from the output files, not estimated.

#### Scenario: All categories are present

- **WHEN** the datasets contain no `geothermal` facility
- **THEN** `stats.json` has `by_energy.geothermal` equal to 0

#### Scenario: Mixed facilities count under each of their sources

- **WHEN** the datasets contain one facility with `energy_sources` `["coal","gas"]` and one with `["gas"]`
- **THEN** `by_energy.mixed` is 1, `by_energy.gas` is 1, `by_energy_source.coal` is 1, and `by_energy_source.gas` is 2

#### Scenario: Counts agree with the datasets

- **WHEN** `stats.json` is generated
- **THEN** `facilities` equals the number of features in `plants.geojson`, the sum of `by_energy` values equals `facilities`, and the sum of `by_voltage_class` values equals `lines`

#### Scenario: Official counts agree with the reports

- **WHEN** `unmatched.csv` has 2 rows with reason `unreviewed` and `official_diff.csv` has 1 row
- **THEN** `official.unmatched.unreviewed` is 2 and `official.capacity_discrepancies` is 1


<!-- @trace
source: cross-validate-official-data
updated: 2026-11-12
code:
  - data/official/raw/2026-11-12/thermal_hydro.csv
  - Makefile
  - data/official/raw/2026-11-12/renewable.csv
  - README.md
  - data/processed/dedup_log.csv
  - data/official/raw/2026-11-12/units.json
  - data/processed/unmatched.csv
  - powermap/facilities.py
  - handoff.md
  - powermap/stats.py
  - data/official/crosswalk_candidates.csv
  - data/official/crosswalk.csv
  - data/processed/official_diff.csv
  - data/official/raw/2026-11-12/nuclear.csv
  - powermap/crosswalk.py
  - data/processed/plants.geojson
  - powermap/enrich.py
  - data/official/raw/2026-11-12/manifest.json
  - data/processed/stats.json
  - powermap/official.py
tests:
  - tests/test_crosswalk.py
  - tests/test_official.py
  - tests/test_stats.py
  - tests/test_facilities.py
  - tests/test_enrich.py
-->

---
### Requirement: Terminal summary

After writing `stats.json` the system SHALL print a human-readable summary with the facility count, line count, missing-voltage count, missing-capacity count, excluded rooftop solar count, excluded counts per region outside the main island, and the per-category counts.

#### Scenario: Summary printed after build

- **WHEN** `make data` finishes successfully
- **THEN** the terminal output ends with the statistics summary

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
### Requirement: Substation statistics

The system SHALL add to `stats.json`: `substations` (feature count of `substations.geojson`), `substations_missing_voltage`, and `substations_by_voltage_class` (an object with all five voltage classes `ehv`, `hv`, `mv`, `lv`, `missing` as keys, 0 when absent). The sum of `substations_by_voltage_class` SHALL equal `substations`. The terminal summary SHALL also print the substation count and the substation missing-voltage count. Existing fields of `stats.json` SHALL keep their values.

#### Scenario: Substation counts

##### Example: three substations

- **GIVEN** `substations.geojson` has three substations with `voltage_class` `ehv`, `missing`, `missing`
- **WHEN** `stats.json` is generated
- **THEN** `substations` is 3, `substations_missing_voltage` is 2, and `substations_by_voltage_class` is `{"ehv": 1, "hv": 0, "mv": 0, "lv": 0, "missing": 2}`

#### Scenario: No substations

- **WHEN** `substations.geojson` has no features
- **THEN** `substations` is 0 and every value in `substations_by_voltage_class` is 0

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
### Requirement: Located official plant count

The `official` object in `stats.json` SHALL include `located`, the number of features in `official_points.geojson`. The terminal summary SHALL print it next to the unmatched counts. Other fields of `official` SHALL keep their values.

#### Scenario: Located count

- **WHEN** `official_points.geojson` has 30 features
- **THEN** `stats.official.located` is 30

<!-- @trace
source: locate-official-plants
updated: 2026-11-13
code:
  - data/processed/official_points.geojson
  - web/app.js
  - data/official/crosswalk.csv
  - data/processed/plants.geojson
  - data/processed/unmatched.csv
  - web/lib.js
  - web/style.css
  - data/processed/stats.json
  - data/official/locations.csv
  - web/index.html
  - data/processed/dedup_log.csv
  - powermap/official_points.py
  - Makefile
  - README.md
  - powermap/stats.py
tests:
  - web/tests/lib.test.js
  - tests/test_stats.py
  - tests/test_official_points.py
  - tests/test_make_web.py
-->