## Purpose

Acquire Taipower open data from data.gov.tw, keep each download as a dated, committed snapshot, and normalize it into a plant-level official list with capacity and primary energy so OSM facilities can be cross-validated offline.

## ADDED Requirements

### Requirement: Official snapshot download

The system SHALL provide `make official-download`, which downloads datasets 8934 (`thermal_hydro.csv`), 10858 (`nuclear.csv`), 17141 (`renewable.csv`) and 8931 (`units.json`) into `data/official/raw/<YYYY-MM-DD>/` named after the UTC download date, and writes `manifest.json` in that directory with `downloaded_at`, `license` (`政府資料開放授權條款第1版`) and, per file, `dataset_id`, `title`, `url`, `file` and `sha256`. Files SHALL be written to a temporary directory and moved into place only after all four downloads succeed. The system SHALL refuse to overwrite an existing date directory and exit non-zero. `make data` SHALL NOT access the network for official data.

#### Scenario: Successful download creates a dated snapshot

- **WHEN** `make official-download` runs on 2026-11-12 and all four downloads succeed
- **THEN** `data/official/raw/2026-11-12/` contains the four files and a `manifest.json` whose `files` entries carry the SHA-256 of each file

#### Scenario: Failed download leaves no partial snapshot

- **WHEN** one of the four downloads fails
- **THEN** the command exits non-zero and no `data/official/raw/<date>/` directory is created

#### Scenario: Existing snapshot is not overwritten

- **WHEN** `data/official/raw/2026-11-12/` already exists and the download runs again on the same day
- **THEN** the command exits non-zero with a message naming the existing directory

### Requirement: Official plant normalization

The system SHALL read one snapshot directory (default: the latest date directory, overridable with `OFFICIAL_DIR`) and write `data/interim/official_plants.json` with `source_dir`, `excluded_outside_main_island`, `warnings` and `plants`. Each plant SHALL have `official_id`, `dataset_id`, `name`, `name_normalized`, `county`, `address`, `capacity_mw`, `capacity_by_source_mw`, `energy_primary` and `n_units`. Units SHALL be grouped as follows: datasets 8934 and 10858 by plant name with id `tp-plant:<name>`; dataset 17141 by the Chinese part of the station name (the text before the first `/` after which only ASCII characters remain, so `中科E/S太陽光電發電站/Zhongke E/S Solar Power Station` gives `中科E/S太陽光電發電站`) with id `tp-re:<name>`, skipping rows without an energy type; dataset 8931 only rows whose unit type starts with `民營電廠-` and whose unit name is not `小計`, grouped by the unit name text before `#` with id `ipp:<name>`. Capacities SHALL be converted to MW (kW ÷ 1000) and summed per plant. `county` SHALL be the first three characters of the address with `臺` replaced by `台`, or `null` when the source has no address. When a required column is missing from a source file the system SHALL exit non-zero naming the missing column.

#### Scenario: Units are summed into a plant

- **WHEN** `thermal_hydro.csv` has 7 units of `大潭發電廠` totaling 4,984,200 kW
- **THEN** `official_plants.json` has one plant `tp-plant:大潭發電廠` with `capacity_mw` 4984.2 and `n_units` 7

#### Scenario: Private plant units come from the real-time list

- **WHEN** `units.json` has rows `民營電廠-燃氣 海湖#1 450.0`, `民營電廠-燃氣 海湖#2 450.0`, `民營電廠-燃氣 小計 6389.7(10.408%)` and `燃氣 大潭CC#1 742.7`
- **THEN** the only plant from this file is `ipp:海湖` with `capacity_mw` 900.0, `county` `null` and `energy_primary` `gas`

#### Scenario: Missing column fails loudly

- **WHEN** `thermal_hydro.csv` lacks the column `裝置容量(瓩)`
- **THEN** the command exits non-zero and the message contains `裝置容量(瓩)`

### Requirement: Official fuel mapping and primary energy

The system SHALL map official fuel and energy types to source categories: `水` → `hydro`; `煤` and `燃煤` → `coal`; `天然氣` and `燃氣` → `gas`; nuclear dataset units → `nuclear`; `太陽能` → `solar`; `陸域風力` and `離岸風力` → `wind`; `地熱` → `geothermal`; `重油`, `輕柴油` and any other value → `other`. An unrecognized value SHALL also add a warning naming it. `capacity_by_source_mw` SHALL sum unit capacity per category. `energy_primary` SHALL be the category with the largest capacity; ties SHALL be broken by the order `solar, wind, hydro, gas, coal, nuclear, geothermal, other`.

#### Scenario: Mixed-fuel plant gets the larger fuel as primary

- **WHEN** `興達發電廠` has coal units totaling 1,100 MW and gas units totaling 2,225.95 MW
- **THEN** its `energy_primary` is `gas`

##### Example: fuel mapping

| Official value | Category | Warning |
| --- | --- | --- |
| 水 | hydro | no |
| 煤 | coal | no |
| 天然氣 | gas | no |
| 民營電廠-燃煤 | coal | no |
| 重油 | other | no |
| 輕柴油 | other | no |
| 離岸風力/Offshore Wind | wind | no |
| 生質能 | other | yes |

### Requirement: Official scope filter

Plants whose `county` is `金門縣`, `連江縣` or `澎湖縣` SHALL be excluded from `plants` and counted in `excluded_outside_main_island`. Plants with `county` `null` SHALL be kept.

#### Scenario: Outlying island plants are excluded

- **WHEN** the snapshot contains `塔山發電廠` (金門縣), `協和電廠－珠山分廠` (連江縣) and `尖山發電廠` (澎湖縣)
- **THEN** none of them appears in `plants` and `excluded_outside_main_island` is 3
