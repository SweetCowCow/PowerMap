## MODIFIED Requirements

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
