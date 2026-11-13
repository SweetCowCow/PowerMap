## MODIFIED Requirements

### Requirement: Map data loading

The web page SHALL load `data/plants.geojson`, `data/lines.geojson`, `data/substations.geojson`, `data/official_points.geojson`, `data/official_status.json`, `data/stats.json`, `data/counties.geojson` and `data/official_diff.csv` relative to the page. When any of the first seven fails to load, the page SHALL show an error banner naming each failed file and SHALL NOT render an empty map silently. When only `official_diff.csv` fails, the page SHALL render normally without capacity-difference lines in popups.

#### Scenario: Missing data file

- **WHEN** `data/lines.geojson` returns HTTP 404
- **THEN** a banner reads that `lines.geojson` failed to load

#### Scenario: Missing substation file

- **WHEN** `data/substations.geojson` returns HTTP 404
- **THEN** a banner reads that `substations.geojson` failed to load

#### Scenario: Missing official point file

- **WHEN** `data/official_points.geojson` returns HTTP 404
- **THEN** a banner reads that `official_points.geojson` failed to load

#### Scenario: Missing official status file

- **WHEN** `data/official_status.json` returns HTTP 404
- **THEN** a banner reads that `official_status.json` failed to load

#### Scenario: Missing difference report

- **WHEN** `data/official_diff.csv` returns HTTP 404 and the other files load
- **THEN** the map renders facilities and lines and no error banner is shown

## ADDED Requirements

### Requirement: Operating status display

For a facility with an `official_id`, and for an official point, the page SHALL look up `official_status.json` by `official_id`. When the status is `retired` or `mothballed`, the symbol SHALL use the inactive colour `#5c6773` instead of its energy colour (the nuclear diamond outline and the official point ring included); `partially_retired` and plants without a status SHALL keep their normal colours. When a status exists, the popup SHALL add a 運轉狀態 row with the label (已停止運轉, 封存, 部分機組已除役) followed by `since` when present, a 機組 row when `units` is present, a 備註 row when `note` is present, and a link to `source`; all text SHALL be HTML-escaped. Plants without a status SHALL show no status row. The legend SHALL explain the inactive colour. Filters and statistics SHALL NOT change because of status.

#### Scenario: Status symbols and rows

##### Example: status display

| Plant | status | since | Symbol | Popup |
| --- | --- | --- | --- | --- |
| 核一廠 (nuclear) | retired | 2019-07 | grey diamond | 運轉狀態 已停止運轉（2019-07）, source link |
| 龍門廠 (official point) | mothballed | empty | grey dashed ring | 運轉狀態 封存, source link |
| 協和發電廠 | partially_retired | 2019 | normal colour | 運轉狀態 部分機組已除役（2019）, 機組 row |
| 台中發電廠 | none | – | normal colour | no 運轉狀態 row |
