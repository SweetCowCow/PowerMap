## MODIFIED Requirements

### Requirement: Map data loading

The web page SHALL load `data/plants.geojson`, `data/lines.geojson`, `data/substations.geojson`, `data/stats.json`, `data/counties.geojson` and `data/official_diff.csv` relative to the page. When any of the first five fails to load, the page SHALL show an error banner naming each failed file and SHALL NOT render an empty map silently. When only `official_diff.csv` fails, the page SHALL render normally without capacity-difference lines in popups.

#### Scenario: Missing data file

- **WHEN** `data/lines.geojson` returns HTTP 404
- **THEN** a banner reads that `lines.geojson` failed to load

#### Scenario: Missing substation file

- **WHEN** `data/substations.geojson` returns HTTP 404
- **THEN** a banner reads that `substations.geojson` failed to load

#### Scenario: Missing difference report

- **WHEN** `data/official_diff.csv` returns HTTP 404 and the other files load
- **THEN** the map renders facilities and lines and no error banner is shown

## ADDED Requirements

### Requirement: Substation layer

The page SHALL draw each substation as a square: filled with its voltage class colour from the line palette when `voltage_class` is not `missing`, and as a hollow `#8a94a0` square when it is `missing`. Symbol size SHALL NOT vary with voltage or capacity. Substations SHALL stay clickable after facilities have been shown, and lines and facilities SHALL stay clickable while substations are shown. Each voltage checkbox SHALL show both its line count and its substation count. The voltage filter section SHALL include a 變電所 toggle, on by default. A substation SHALL be visible exactly when the toggle is on, its `voltage_class` is checked, and, in data gap mode, its `missing_voltage` is true. Clicking a substation SHALL open a popup with its name (未命名變電所 when null), type label, maximum voltage (未填 when null), `voltage_raw`, operator (未填 when null) and an OSM link, with all data text HTML-escaped and never showing `null` or `undefined`. The search box SHALL list matching substations by name in a separate group of up to 8 results, and selecting one SHALL move the map to it and open its popup. The statistics SHALL show the visible substation count with its total under 目前顯示, and the substation missing-voltage total under 全部資料.

#### Scenario: Substation visibility

##### Example: visibility rules

| voltage_class | missing_voltage | Toggle | Checked classes | Gap mode | Visible |
| --- | --- | --- | --- | --- | --- |
| ehv | false | on | all | off | yes |
| ehv | false | off | all | off | no |
| ehv | false | on | all except ehv | off | no |
| missing | true | on | all | on | yes |
| hv | false | on | all | on | no |

#### Scenario: Type labels

##### Example: substation type

| substation | Label |
| --- | --- |
| transmission | 輸電 |
| distribution | 配電 |
| minor_distribution | 小型配電 |
| traction | 鐵路供電 |
| yes | 未填 |
| null | 未填 |
| windfarm | windfarm |

#### Scenario: Clickable after showing facilities

- **WHEN** the user checks all energies, then unchecks them, then clicks a substation and a line
- **THEN** a popup opens for each

#### Scenario: Substation search

- **WHEN** the user types the name of a substation
- **THEN** the results list it under a 變電所 group, and selecting it opens its popup
