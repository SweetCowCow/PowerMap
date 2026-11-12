## Purpose

Summarize the facility and line datasets into a single `stats.json` that records the snapshot time and the counts the web map and README rely on, including how much data is missing.

## ADDED Requirements

### Requirement: Statistics file

The system SHALL write `data/processed/stats.json` containing: `snapshot` (from the extraction summary, `null` when unknown), `built_at` (ISO 8601 UTC time of the stats run), `facilities` (feature count of `plants.geojson`), `lines` (feature count of `lines.geojson`), `lines_missing_voltage`, `facilities_missing_capacity`, `by_energy` (an object with all ten energy categories as keys: `solar`, `wind`, `hydro`, `gas`, `coal`, `nuclear`, `geothermal`, `other`, `mixed`, `unknown`), `by_energy_source` (an object with the eight source categories `solar`, `wind`, `hydro`, `gas`, `coal`, `nuclear`, `geothermal`, `other` as keys, counting each facility once for every category in its `energy_sources`), `by_voltage_class` (an object with all five voltage classes as keys), `excluded_rooftop_solar`, and `excluded_outside_main_island` (an object with keys `kinmen`, `matsu`, `penghu`, `other`, copied from the extraction summary, counting raw OSM features). Categories with no features SHALL appear with value 0. Every count SHALL be computed from the output files, not estimated.

#### Scenario: All categories are present

- **WHEN** the datasets contain no `geothermal` facility
- **THEN** `stats.json` has `by_energy.geothermal` equal to 0

#### Scenario: Mixed facilities count under each of their sources

- **WHEN** the datasets contain one facility with `energy_sources` `["coal","gas"]` and one with `["gas"]`
- **THEN** `by_energy.mixed` is 1, `by_energy.gas` is 1, `by_energy_source.coal` is 1, and `by_energy_source.gas` is 2

#### Scenario: Counts agree with the datasets

- **WHEN** `stats.json` is generated
- **THEN** `facilities` equals the number of features in `plants.geojson`, the sum of `by_energy` values equals `facilities`, and the sum of `by_voltage_class` values equals `lines`

### Requirement: Terminal summary

After writing `stats.json` the system SHALL print a human-readable summary with the facility count, line count, missing-voltage count, missing-capacity count, excluded rooftop solar count, excluded counts per region outside the main island, and the per-category counts.

#### Scenario: Summary printed after build

- **WHEN** `make data` finishes successfully
- **THEN** the terminal output ends with the statistics summary
