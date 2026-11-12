## MODIFIED Requirements

### Requirement: Facility value provenance

Each facility SHALL carry `capacity_source` and `energy_data_source`. `capacity_source` SHALL be `osm` when `capacity_mw` comes from the OSM output tag, `taipower` when it was filled from an official plant by the official enrichment, and `null` when `capacity_mw` is `null`. `energy_data_source` SHALL be `osm` when `energy` is not `unknown` and `null` when `energy` is `unknown`.

#### Scenario: Provenance follows the value

- **WHEN** a plant has `plant:output:electricity=550 MW` and no source tag
- **THEN** it has `capacity_source` `osm` and `energy_data_source` `null`

#### Scenario: Filled capacity is marked as official

- **WHEN** a plant without an output tag receives its capacity from an official plant
- **THEN** it has `capacity_source` `taipower` and `missing_capacity` `false`

### Requirement: Facility dataset output

The facility step SHALL write `data/interim/facilities_osm.geojson` and `data/interim/dedup_log_osm.csv`; the official enrichment step SHALL read them and write the final `data/processed/plants.geojson` and `data/processed/dedup_log.csv` (the OSM rows followed by the official merge rows). `plants.geojson` SHALL be a GeoJSON FeatureCollection of Points in EPSG:4326. Each Feature's properties SHALL contain exactly, in this order: `osm_id` (`n`, `w`, or `r` followed by the numeric id), `osm_url` (`https://www.openstreetmap.org/{node|way|relation}/{id}`), `kind` (`plant` or `generator`), `name` (the `name` tag; falls back to `name:zh`, then `null` when both are absent), `operator`, `energy`, `energy_sources`, `energy_data_source`, `source_raw`, `capacity_mw`, `capacity_raw`, `capacity_source`, `n_generators`, `geom_src`, `missing_capacity`, `missing_energy`, `official_id`, `energy_primary`, `energy_primary_source`. In `facilities_osm.geojson` the last three SHALL be `null`. `missing_energy` SHALL be `true` exactly when `energy` is `unknown`. Absent values SHALL be JSON `null`, never `0` or an empty string, except `n_generators`, which is an integer count, and `energy_sources`, which is an array that is empty when no source is known. Both dedup logs SHALL have header `action,kept_osm_id,dropped_osm_id,reason,distance_m`.

#### Scenario: Missing values stay null

- **WHEN** a plant has no `operator` tag and no output tag and is not in the crosswalk
- **THEN** its properties have `operator` `null`, `capacity_mw` `null`, `capacity_raw` `null`, `missing_capacity` `true`, `official_id` `null` and `energy_primary` `null`

#### Scenario: OSM identifiers are traceable

- **WHEN** a facility comes from way 123456
- **THEN** its `osm_id` is `w123456` and its `osm_url` is `https://www.openstreetmap.org/way/123456`

#### Scenario: Final dedup log contains both kinds of rows

- **WHEN** the facility step merged one same-name node and the enrichment merged one official duplicate
- **THEN** `data/processed/dedup_log.csv` has a `same_name_nearby` row followed by an `official_same_plant` row
