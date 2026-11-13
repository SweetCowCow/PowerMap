# web-map-publishing Specification

## Purpose

Build the static web map from committed data files and publish it to GitHub Pages automatically, without rerunning the Python data pipeline in CI.

## Requirements

### Requirement: Static site build

The system SHALL provide `make web`, which creates `web/data/` and copies `plants.geojson`, `lines.geojson`, `substations.geojson`, `stats.json`, `official_diff.csv` and `counties.geojson` from `data/processed/` into it. `make web` SHALL NOT trigger any data pipeline step, even when pipeline outputs are older than their inputs or when no OSM snapshot exists. When a source file is missing, `make web` SHALL exit non-zero. `web/data/` SHALL be ignored by git. `make all` SHALL run `data` then `web`.

#### Scenario: Build without OSM snapshot

- **WHEN** `make web` runs in a fresh clone with no `data/raw/taiwan-latest.osm.pbf`
- **THEN** it copies the six files and does not run uv or any pipeline module

#### Scenario: Missing source

- **WHEN** `data/processed/substations.geojson` does not exist
- **THEN** `make web` exits non-zero


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
### Requirement: Web unit tests

The system SHALL provide `make test-web`, which runs `node --test` over `web/tests/` using only Node built-in modules, with no `package.json` or npm dependency.

#### Scenario: Tests run without npm install

- **WHEN** `make test-web` runs on a machine with Node 22 and no `node_modules`
- **THEN** the tests execute and the command exits 0 when they pass

---
### Requirement: GitHub Pages deployment

The repository SHALL contain a GitHub Actions workflow that runs on push to `main` and on manual dispatch, runs `make test-web` and `make web`, and deploys the `web/` directory to GitHub Pages. A failing `make test-web` or `make web` SHALL stop the run before deployment. The workflow SHALL NOT run the Python data pipeline.

#### Scenario: Test failure blocks deploy

- **WHEN** a push to `main` contains a failing web test
- **THEN** the workflow fails and the deploy job does not run

#### Scenario: Successful deploy

- **WHEN** a push to `main` passes the tests
- **THEN** the site at the repository's GitHub Pages URL serves the new `web/` content including `web/data/`