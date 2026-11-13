# county-boundary-dataset Specification

## Purpose

Download the national county boundary dataset and turn it into a small, simplified GeoJSON of the counties covered by the power data, so the web map can draw Taiwan's outline without depending on external map tiles.

## Requirements

### Requirement: Boundary download

The system SHALL provide `make boundaries`, which downloads the SHP zip of data.gov.tw dataset 7442 ("直轄市、縣市界線(TWD97經緯度)") to `data/raw/boundaries/` when the zip is not already present, and skips the download when it is present. The download URL SHALL default to the TGOS SHP URL recorded in the design and SHALL be overridable with the `BOUNDARY_URL` variable. A failed download SHALL exit with a non-zero status and SHALL NOT leave a partial zip in place. `make data` SHALL NOT run this step.

#### Scenario: Zip already present

- **WHEN** `make boundaries` runs and the zip file exists under `data/raw/boundaries/`
- **THEN** no network request is made and the existing zip is used

#### Scenario: Download fails

- **WHEN** the server returns HTTP 404
- **THEN** the command exits non-zero and no zip file remains under `data/raw/boundaries/`

---
### Requirement: Boundary simplification and scope

The system SHALL read the county polygons, drop the counties 澎湖縣, 金門縣 and 連江縣, simplify each remaining geometry in EPSG:3826 with a tolerance of 100 m while preserving topology, transform back to EPSG:4326, and round every coordinate to 5 decimal places. Each output Feature SHALL have exactly one property, `name`, holding the county name from the source. Counties SHALL NOT be merged or clipped.

#### Scenario: Outlying counties are dropped

- **WHEN** the source contains 22 counties including 澎湖縣, 金門縣 and 連江縣
- **THEN** the output contains 19 Features and none is named 澎湖縣, 金門縣 or 連江縣

#### Scenario: Properties and precision

- **WHEN** a source county has attributes `COUNTYNAME`, `COUNTYCODE`, `COUNTYENG`
- **THEN** its output Feature has properties `{"name": "<COUNTYNAME>"}` only, and no coordinate has more than 5 decimal places

---
### Requirement: Boundary output with provenance

The system SHALL write `data/processed/counties.geojson` as a FeatureCollection with a top-level `source` object containing `dataset` (`"data.gov.tw/7442"`), `url`, `downloaded_at` (ISO 8601 UTC, from the zip file's modification time), `sha256` (of the zip) and `license` (`"政府資料開放授權條款第1版"`). The output file is committed to git; the raw zip is not.

#### Scenario: Provenance recorded

- **WHEN** `make boundaries` completes
- **THEN** `counties.geojson` has a `source.sha256` equal to the SHA-256 of the zip under `data/raw/boundaries/`, and `git check-ignore` reports the zip as ignored
