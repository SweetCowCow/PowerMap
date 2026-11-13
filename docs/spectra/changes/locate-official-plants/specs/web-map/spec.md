## MODIFIED Requirements

### Requirement: Map data loading

The web page SHALL load `data/plants.geojson`, `data/lines.geojson`, `data/substations.geojson`, `data/official_points.geojson`, `data/stats.json`, `data/counties.geojson` and `data/official_diff.csv` relative to the page. When any of the first six fails to load, the page SHALL show an error banner naming each failed file and SHALL NOT render an empty map silently. When only `official_diff.csv` fails, the page SHALL render normally without capacity-difference lines in popups.

#### Scenario: Missing data file

- **WHEN** `data/lines.geojson` returns HTTP 404
- **THEN** a banner reads that `lines.geojson` failed to load

#### Scenario: Missing substation file

- **WHEN** `data/substations.geojson` returns HTTP 404
- **THEN** a banner reads that `substations.geojson` failed to load

#### Scenario: Missing official point file

- **WHEN** `data/official_points.geojson` returns HTTP 404
- **THEN** a banner reads that `official_points.geojson` failed to load

#### Scenario: Missing difference report

- **WHEN** `data/official_diff.csv` returns HTTP 404 and the other files load
- **THEN** the map renders facilities and lines and no error banner is shown

## ADDED Requirements

### Requirement: Official estimated location layer

The page SHALL draw each feature of `official_points.geojson` as a hollow dashed circle outlined in the colour of its `energy_primary` (unknown colour when null), visually distinct from the filled OSM facility symbols, and SHALL keep lines, facilities and substations clickable. The energy filter section SHALL include a 台電資料（估計位置） toggle, on by default. An official point SHALL be visible exactly when the toggle is on, data gap mode is off, and its `energy_primary` is checked (unknown when null). Clicking one SHALL open a popup stating that the position is estimated from the official address and is not OSM data, with name, capacity, primary energy, address, precision label (門牌、地號、村里中心、路段、廠區、外海) and check date, all HTML-escaped and never showing `null` or `undefined`. The search box SHALL list matching official points by name in a separate 台電資料 group. The statistics SHALL show the visible official point count with its total under 目前顯示, and SHALL show how many of the unmatched official plants have an estimated location.

#### Scenario: Official point visibility

##### Example: visibility rules

| energy_primary | Toggle | Checked energies | Gap mode | Visible |
| --- | --- | --- | --- | --- |
| solar | on | solar | off | yes |
| solar | off | solar | off | no |
| solar | on | wind | off | no |
| solar | on | solar | on | no |
| null | on | unknown | off | yes |

#### Scenario: Estimate is stated in the popup

- **WHEN** the user clicks an official point with `precision` `village`
- **THEN** the popup says the position is estimated from the official address, is not OSM data, and shows 村里中心 as the precision
