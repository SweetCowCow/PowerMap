## MODIFIED Requirements

### Requirement: Static site build

The system SHALL provide `make web`, which creates `web/data/` and copies `plants.geojson`, `lines.geojson`, `substations.geojson`, `stats.json`, `official_diff.csv` and `counties.geojson` from `data/processed/` into it. `make web` SHALL NOT trigger any data pipeline step, even when pipeline outputs are older than their inputs or when no OSM snapshot exists. When a source file is missing, `make web` SHALL exit non-zero. `web/data/` SHALL be ignored by git. `make all` SHALL run `data` then `web`.

#### Scenario: Build without OSM snapshot

- **WHEN** `make web` runs in a fresh clone with no `data/raw/taiwan-latest.osm.pbf`
- **THEN** it copies the six files and does not run uv or any pipeline module

#### Scenario: Missing source

- **WHEN** `data/processed/substations.geojson` does not exist
- **THEN** `make web` exits non-zero
