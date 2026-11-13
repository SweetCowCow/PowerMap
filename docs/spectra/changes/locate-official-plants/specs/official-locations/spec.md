## Purpose

Keep a human-reviewed table of estimated locations for official plants that have no OSM counterpart, and turn it into a point dataset so the web map can show them clearly marked as address-based estimates rather than OSM data.

## ADDED Requirements

### Requirement: Official location table validation

The system SHALL read `data/official/locations.csv` with columns `official_id,lat,lon,precision,method,source,checked_at,note`, where `precision` is one of `address`, `parcel`, `village`, `road`, `site`, `offshore` and `method` is one of `nominatim`, `manual`. The system SHALL exit non-zero, printing the offending rows, when an `official_id` appears more than once, when `precision` or `method` has another value, or when `lat` or `lon` is not a number or lies outside the main island bounding box. A row whose `official_id` is not in the official plant list SHALL print a warning and be ignored. A row whose `official_id` has crosswalk relation `same` or `part` SHALL print a warning and be ignored. When `locations.csv` does not exist, the system SHALL treat it as empty.

#### Scenario: Invalid rows

##### Example: validation

| Row problem | Result |
| --- | --- |
| `official_id` listed twice | exit non-zero, both rows printed |
| `precision` = `exact` | exit non-zero, row printed |
| `lat` = `abc` | exit non-zero, row printed |
| `lat` = `26.15`, `lon` = `119.95` (outside main island box) | exit non-zero, row printed |
| `official_id` = `tp-re:不存在` | warning, row ignored |
| `official_id` linked with `part` in the crosswalk | warning, row ignored |

#### Scenario: Missing table

- **WHEN** `data/official/locations.csv` does not exist
- **THEN** the step succeeds and writes an empty FeatureCollection

### Requirement: Official point output

The system SHALL write `data/processed/official_points.geojson` as a FeatureCollection of Points, one per valid location row, with coordinates from `lon`, `lat` rounded to 5 decimals and properties, in order, `official_id`, `name`, `county`, `address`, `capacity_mw`, `energy_primary` (from the official plant list), `precision`, `method`, `source`, `checked_at`. Features SHALL be sorted by `official_id`. `unmatched.csv` SHALL NOT change because of the location table.

#### Scenario: Located official plant

- **GIVEN** official plant `tp-re:中科E/S太陽光電發電站` with relation `none`, address `台中市西屯區科園一路1號`, capacity 0.198 MW, primary energy `solar`
- **WHEN** `locations.csv` has `tp-re:中科E/S太陽光電發電站,24.20811,120.61822,address,nominatim,科園一路1號,2026-11-13,`
- **THEN** `official_points.geojson` has a Point at `[120.61822, 24.20811]` with `capacity_mw` 0.198, `energy_primary` `solar`, `precision` `address`, and the plant still appears in `unmatched.csv` with reason `no_osm`
