## Purpose

Link official plants to OSM facilities through a human-reviewed crosswalk file, then use the links to fill missing capacity, add primary energy, merge duplicate OSM facilities and report discrepancies and unmatched official plants.

## ADDED Requirements

### Requirement: Name normalization

The system SHALL normalize plant names by applying NFKC, replacing `臺` with `台`, removing whitespace, removing a trailing English name (the text from the first `/` after which only ASCII characters remain), removing a leading `台電` or `台灣電力公司`, and then repeatedly removing a trailing `發電廠`, `發電站`, `電廠`, `分廠` or `廠` until none remains.

#### Scenario: Different spellings normalize to the same name

- **WHEN** the names `台電大潭發電廠` and `大潭發電廠` are normalized
- **THEN** both become `大潭`

##### Example: normalization

| Input | Output |
| --- | --- |
| 台電大潭發電廠 | 大潭 |
| 臺中發電廠 | 台中 |
| 核三廠 | 核三 |
| 石門風力發電站/Shimen Wind Power Station | 石門風力 |
| 協和電廠－珠山分廠 | 協和電廠－珠山 |
| 中科E/S太陽光電發電站/Zhongke E/S Solar Power Station | 中科E/S太陽光電 |
| 大潭 | 大潭 |

### Requirement: Crosswalk candidates

The system SHALL provide `make crosswalk-candidates`, which writes `data/official/crosswalk_candidates.csv` with columns `official_id,official_name,county,official_capacity_mw,osm_id,osm_name,osm_kind,osm_capacity_mw,lon,lat,osm_url,match_type`. For each official plant, every named OSM facility whose normalized name equals the official normalized name SHALL produce a row with `match_type` `exact`, and every named OSM facility where one normalized name contains the other and the shorter one has at least 2 characters SHALL produce a row with `match_type` `contains`. An official plant without any candidate SHALL produce one row with `match_type` `none` and empty OSM columns. The pipeline SHALL NOT read this file.

#### Scenario: Containment produces a candidate

- **WHEN** the official plant is `興達發電廠` and an OSM way is named `3900MW興達複循環燃煤電廠`
- **THEN** the candidates file has a row pairing them with `match_type` `contains`

#### Scenario: Official plant without candidates is listed

- **WHEN** no OSM facility name relates to `核三廠`
- **THEN** the candidates file has a row for `tp-plant:核三廠` with `match_type` `none` and empty OSM columns

### Requirement: Crosswalk file validation

The pipeline SHALL read `data/official/crosswalk.csv` with columns `official_id,osm_ids,relation,note`, where `osm_ids` is a `;`-separated list and `relation` is `same`, `part` or `none`. The system SHALL exit non-zero, printing the conflicting rows, when an `official_id` appears in more than one row, when an OSM id appears in more than one row, or when `relation` has another value. A row whose `official_id` is not in `official_plants.json` SHALL print a warning and be ignored. An OSM id not present in the facility dataset SHALL print a warning and be ignored; when all ids of a `same` or `part` row are ignored, the official plant SHALL be reported as unmatched with reason `osm_missing`.

#### Scenario: OSM id used twice is rejected

- **WHEN** `w661662183` appears in the rows of both `tp-plant:大潭發電廠` and `tp-plant:通霄發電廠`
- **THEN** the pipeline exits non-zero and prints both rows

#### Scenario: Stale OSM id is ignored with a warning

- **WHEN** a `same` row lists `w1;w999` and `w999` is not in the facility dataset
- **THEN** a warning names `w999` and the row applies to `w1` only

### Requirement: Official enrichment

For a `same` row, the facilities listed SHALL be merged into the first listed id that exists; the kept facility's `n_generators` SHALL increase by the dropped facilities' `n_generators`, and each dropped facility SHALL be written to `dedup_log.csv` with action `official_same_plant`, `reason` equal to the `official_id` and the distance in meters computed in EPSG:3826. When the kept facility has `capacity_mw` `null`, it SHALL receive the official `capacity_mw` with `capacity_source` `taipower` and `missing_capacity` `false`; an OSM capacity SHALL never be overwritten. For a `part` row, each listed facility SHALL be kept separately and capacity SHALL NOT be filled. For both `same` and `part`, each resulting facility SHALL get `official_id`, `energy_primary` from the official plant and `energy_primary_source` `taipower`. Facilities not referenced by the crosswalk SHALL keep `official_id`, `energy_primary` and `energy_primary_source` `null`. `energy`, `energy_sources` and `energy_data_source` SHALL NOT change.

#### Scenario: Duplicate plant areas are merged and filled

- **WHEN** the crosswalk has `tp-plant:大潭發電廠,r18726493;w661662183,same,` and `r18726493` has no capacity
- **THEN** `plants.geojson` contains `r18726493` but not `w661662183`, `r18726493` has `capacity_mw` 4984.2 and `capacity_source` `taipower`, and `dedup_log.csv` has a row `official_same_plant,r18726493,w661662183,tp-plant:大潭發電廠,<distance>`

#### Scenario: OSM capacity is not overwritten

- **WHEN** a `same` row links a facility with OSM `capacity_mw` 4326 to an official plant of 3325.95 MW whose `energy_primary` is `gas`
- **THEN** the facility keeps `capacity_mw` 4326 and `capacity_source` `osm`, and gets `energy_primary` `gas` and `energy_primary_source` `taipower`

#### Scenario: Part relation keeps facilities apart

- **WHEN** the crosswalk has `tp-plant:大甲溪發電廠,w1;w2,part,` and neither facility has capacity
- **THEN** both `w1` and `w2` remain, both have `official_id` `tp-plant:大甲溪發電廠`, and both keep `capacity_mw` `null`

### Requirement: Discrepancy and unmatched reports

The system SHALL write `data/processed/official_diff.csv` with columns `official_id,osm_id,osm_capacity_mw,official_capacity_mw,diff_ratio`, listing each `same` link where the kept facility has an OSM capacity and |OSM − official| ÷ official exceeds the threshold (default 0.2, configurable with `--capacity-diff-threshold` and the Makefile variable `CAPACITY_DIFF_THRESHOLD`), with `diff_ratio` rounded to 3 decimals. The system SHALL write `data/processed/unmatched.csv` with columns `official_id,name,county,capacity_mw,reason`, listing official plants with relation `none` (reason `no_osm`), official plants absent from the crosswalk (reason `unreviewed`), and plants whose crosswalk ids were all ignored (reason `osm_missing`). The terminal output SHALL report the number of `unreviewed` plants and ignored crosswalk ids.

#### Scenario: Large difference is reported

- **WHEN** a `same` link has OSM 4326 MW and official 3325.95 MW with the default threshold
- **THEN** `official_diff.csv` has a row with `diff_ratio` 0.301

#### Scenario: Difference at the threshold is not reported

- **WHEN** a `same` link has OSM 120 MW and official 100 MW with threshold 0.2
- **THEN** `official_diff.csv` has no row for it

#### Scenario: Unreviewed official plant is listed

- **WHEN** `ipp:海湖` is in `official_plants.json` but not in the crosswalk
- **THEN** `unmatched.csv` has a row for `ipp:海湖` with reason `unreviewed`
