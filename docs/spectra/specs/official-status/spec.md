# official-status Specification

## Purpose

Keep a human-reviewed table of operating status for official plants, such as retired or mothballed nuclear plants, with a public source for every entry, and publish it as a lookup file so the web map can mark plants that no longer generate.

## Requirements

### Requirement: Official status table validation

The system SHALL read `data/official/status.csv` with columns `official_id,status,since,units,source,checked_at,note`, where `status` is one of `retired`, `mothballed`, `partially_retired`; `since` is empty or a date in the form `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; `source` starts with `http://` or `https://`; and `checked_at` is a date `YYYY-MM-DD`. The system SHALL exit non-zero, printing the offending rows, when an `official_id` appears more than once or any of these rules is broken. A row whose `official_id` is not in the official plant list SHALL print a warning and be ignored. When `status.csv` does not exist, the system SHALL treat it as empty.

#### Scenario: Invalid rows

##### Example: validation

| Row problem | Result |
| --- | --- |
| `official_id` listed twice | exit non-zero, both rows printed |
| `status` = `closed` | exit non-zero, row printed |
| `since` = `2019/07` | exit non-zero, row printed |
| `source` = `台電新聞稿` | exit non-zero, row printed |
| `checked_at` = `2026-11` | exit non-zero, row printed |
| `official_id` = `tp-plant:不存在` | warning, row ignored |

#### Scenario: Missing table

- **WHEN** `data/official/status.csv` does not exist
- **THEN** the step succeeds and writes `{}`


<!-- @trace
source: plant-operating-status
updated: 2026-11-13
code:
  - data/processed/stats.json
  - powermap/official.py
  - powermap/official_status.py
  - Makefile
  - data/processed/dedup_log.csv
  - data/processed/official_status.json
  - README.md
  - web/app.js
  - web/index.html
  - web/style.css
  - web/lib.js
  - powermap/substations.py
  - data/processed/plants.geojson
  - data/processed/substations.geojson
  - data/official/crosswalk.csv
  - data/processed/substation_dedup_log.csv
  - powermap/refresh_report.py
  - data/official/status.csv
tests:
  - tests/test_make_web.py
  - web/tests/lib.test.js
  - tests/test_official.py
  - tests/test_official_status.py
  - tests/test_refresh_report.py
  - tests/test_substations.py
-->

---
### Requirement: Official status output

The system SHALL write `data/processed/official_status.json` as a JSON object keyed by `official_id`, with keys sorted, where each value has, in order, `status`, `since`, `units`, `source`, `checked_at`, `note`, and empty cells are written as `null`.

#### Scenario: Retired nuclear plant

- **GIVEN** official plant `tp-plant:核一廠`
- **WHEN** `status.csv` has `tp-plant:核一廠,retired,2019-07,一號機 2018-12 停機；二號機 2019-07 停機,https://www.taipower.com.tw/example,2026-11-13,`
- **THEN** `official_status.json` has key `tp-plant:核一廠` with `status` `retired`, `since` `2019-07`, `units` `一號機 2018-12 停機；二號機 2019-07 停機`, `source` `https://www.taipower.com.tw/example`, `checked_at` `2026-11-13` and `note` `null`

<!-- @trace
source: plant-operating-status
updated: 2026-11-13
code:
  - data/processed/stats.json
  - powermap/official.py
  - powermap/official_status.py
  - Makefile
  - data/processed/dedup_log.csv
  - data/processed/official_status.json
  - README.md
  - web/app.js
  - web/index.html
  - web/style.css
  - web/lib.js
  - powermap/substations.py
  - data/processed/plants.geojson
  - data/processed/substations.geojson
  - data/official/crosswalk.csv
  - data/processed/substation_dedup_log.csv
  - powermap/refresh_report.py
  - data/official/status.csv
tests:
  - tests/test_make_web.py
  - web/tests/lib.test.js
  - tests/test_official.py
  - tests/test_official_status.py
  - tests/test_refresh_report.py
  - tests/test_substations.py
-->