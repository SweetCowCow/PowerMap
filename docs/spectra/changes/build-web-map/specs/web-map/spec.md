## Purpose

Present the facility, line and county datasets as a single-page interactive Leaflet map that people can filter and inspect, showing missing values honestly and never implying capacity or power flow through symbol size.

## ADDED Requirements

### Requirement: Map data loading

The web page SHALL load `data/plants.geojson`, `data/lines.geojson`, `data/stats.json`, `data/counties.geojson` and `data/official_diff.csv` relative to the page. When any of the first four fails to load, the page SHALL show an error banner naming each failed file and SHALL NOT render an empty map silently. When only `official_diff.csv` fails, the page SHALL render normally without capacity-difference lines in popups.

#### Scenario: Missing data file

- **WHEN** `data/lines.geojson` returns HTTP 404
- **THEN** a banner reads that `lines.geojson` failed to load

#### Scenario: Missing difference report

- **WHEN** `data/official_diff.csv` returns HTTP 404 and the other files load
- **THEN** the map renders facilities and lines and no error banner is shown

### Requirement: Base layers

The map SHALL use a `#0b1826` background and SHALL show the county outlines from `counties.geojson` as the default base layer, labelled 縣市界（離線）, without requesting any map tiles. A second base layer labelled OSM 圖磚（調暗） SHALL use the OpenStreetMap standard tiles from `tile.openstreetmap.org`, darkened with a CSS filter applied only to that tile layer, with the attribution "© OpenStreetMap contributors". A third base layer labelled OSM 圖磚（原色） SHALL use the same OpenStreetMap tiles without the filter. A fourth base layer labelled 正射影像 SHALL use the 內政部國土測繪中心 PHOTO2 WMTS orthophoto tiles with the attribution "正射影像 © 內政部國土測繪中心". The page SHALL NOT request CARTO tiles. The initial view SHALL fit the Taiwan main island. The page SHALL NOT offer Kinmen, Matsu or Penghu jump controls.

#### Scenario: Default view makes no tile requests

- **WHEN** the page loads with default settings
- **THEN** no request is made to `tile.openstreetmap.org` and county outlines are visible

#### Scenario: Switch to tiles

- **WHEN** the user selects OSM 圖磚（調暗） in the layers control
- **THEN** OSM tiles load beneath the power layers with the darkening filter, power symbols keep their colours, and the attribution "© OpenStreetMap contributors" is shown

#### Scenario: Orthophoto layer

- **WHEN** the user selects 正射影像 in the layers control
- **THEN** tiles load from `wmts.nlsc.gov.tw` beneath the power layers and the attribution names 內政部國土測繪中心

### Requirement: Location tools

The page SHALL provide a county selector listing every county in `counties.geojson`; selecting one SHALL fit the map to that county's bounds. The page SHALL provide a search box that, while the user types, lists up to 8 facilities whose `name` contains the query (case-insensitive), ignoring facilities without a name; selecting a result SHALL move the map to that facility and open its popup even when the facility is hidden by the filters. When the user presses Enter or the place-search button, the page SHALL query OSM Nominatim restricted to Taiwan and list up to 5 results; selecting one SHALL fit the map to its bounding box. The page SHALL NOT send a Nominatim request while the user is typing, SHALL wait at least 1 second between Nominatim requests, and SHALL state that place-search text is sent to Nominatim. A failed or empty Nominatim search SHALL show a message in the result list and SHALL NOT move the map.

#### Scenario: Jump to a county

- **WHEN** the user selects 臺東縣 in the county selector
- **THEN** the map view fits the bounds of the 臺東縣 feature

#### Scenario: Facility name search

##### Example: facility matches

| Query | Facilities | Results |
| --- | --- | --- |
| `大潭` | 大潭發電廠, 大潭風力, null-named generator | 大潭發電廠, 大潭風力 |
| `taichung` | Taichung Power Plant, 台中電廠 | Taichung Power Plant |
| `` (empty) | any | no results |

#### Scenario: Hidden facility from search

- **WHEN** all energy checkboxes are unchecked and the user selects 嘉惠發電廠 from the search results
- **THEN** the map moves to it and its popup opens

#### Scenario: No typing requests to Nominatim

- **WHEN** the user types `台北車站` without pressing Enter
- **THEN** no request is sent to `nominatim.openstreetmap.org`

#### Scenario: Empty place search

- **WHEN** Nominatim returns an empty array for `xyzxyz`
- **THEN** the result list shows that nothing was found and the map does not move

### Requirement: Facility symbols

Facilities SHALL be coloured by `energy`: solar `#ffd15c`, wind `#6fe0c0`, hydro `#5aa9ff`, gas `#ff9a6b`, coal `#e0605f`, other `#b98ad9`, geothermal `#d98a3d`, unknown `#8a94a0`. A `mixed` facility SHALL use the other colour with a dashed white outline. A `nuclear` facility SHALL be drawn as a white hollow diamond. Plants and generators SHALL differ in symbol radius only to distinguish kind, and symbol size SHALL NOT vary with capacity.

#### Scenario: Symbol by energy

##### Example: symbol mapping

| energy | kind | Symbol |
| --- | --- | --- |
| solar | plant | filled circle `#ffd15c`, plant radius |
| wind | generator | filled circle `#6fe0c0`, generator radius |
| mixed | plant | filled circle `#b98ad9` with dashed white outline |
| nuclear | plant | white hollow diamond |
| solar | plant, capacity 500 MW vs 1 MW | same radius for both |

### Requirement: Generator clustering by energy

Facilities with `kind` `generator` SHALL be clustered in one cluster group per `energy` value. A cluster marker SHALL have a fixed size independent of member count, SHALL use its energy colour, and SHALL display the member count. Clustering SHALL be disabled at zoom 12 and above. Facilities with `kind` `plant` SHALL NOT be clustered.

#### Scenario: Clusters keep energy colour

- **WHEN** the map is at zoom 8 and 404 wind generators are visible
- **THEN** wind generators appear as `#6fe0c0` cluster markers showing counts, and no cluster contains both a wind and a solar generator

#### Scenario: Uncluster at high zoom

- **WHEN** the user zooms to 12
- **THEN** every visible generator is drawn individually

#### Scenario: Plants never cluster

- **WHEN** two plants are 50 m apart at zoom 7
- **THEN** both are drawn as individual symbols

### Requirement: Energy filter

The page SHALL offer nine energy checkboxes (solar, wind, hydro, gas, coal, nuclear, geothermal, other, unknown), all unchecked by default, with select-all and select-none controls. A facility SHALL be visible when at least one category in its `energy_sources` is checked, or when its `energy_sources` is empty and unknown is checked. The page SHALL NOT offer a separate mixed checkbox.

#### Scenario: Facilities hidden on first load

- **WHEN** the page loads with default settings
- **THEN** no facility is drawn, the visible facility count is 0, and all 2,515 lines are drawn

#### Scenario: Filter by energy sources

##### Example: visibility

| energy_sources | Checked | Visible |
| --- | --- | --- |
| `["coal","gas"]` | gas | yes |
| `["coal","gas"]` | solar | no |
| `[]` | unknown | yes |
| `[]` | solar, wind | no |
| `["wind"]` | none | no |

### Requirement: Voltage filter and line styles

Lines SHALL be styled by `voltage_class`: ehv `#f0b85a`, hv `#6cc4e8`, mv `#4a7f9c`, lv `#3d5566`, all solid, and missing `#b58aa8` dashed. Line width SHALL NOT vary with voltage or flow. The page SHALL offer five voltage checkboxes, all checked by default, and a line SHALL be visible exactly when its `voltage_class` is checked.

#### Scenario: Hide missing-voltage lines

- **WHEN** the user unchecks 缺電壓
- **THEN** the 1,059 lines with `voltage_class` `missing` are hidden and the other lines remain

### Requirement: Data gap mode

The page SHALL offer a 只看資料缺口 toggle, off by default. When on, a facility SHALL be visible only if it also has `missing_capacity` true, and a line only if it also has `missing_voltage` true; the energy and voltage filters SHALL still apply.

#### Scenario: Gap mode intersects filters

##### Example: gap mode with filters

| Feature | Filter state | Gap mode | Visible |
| --- | --- | --- | --- |
| solar facility, missing_capacity true | solar checked | on | yes |
| solar facility, missing_capacity false | solar checked | on | no |
| solar facility, missing_capacity true | solar unchecked | on | no |
| line, voltage_class missing | missing checked | on | yes |
| line, voltage_class ehv | ehv checked | on | no |

### Requirement: Facility and line popups

Clicking a facility SHALL open a popup with name, kind, energy, capacity, capacity source, operator and an OSM link; plants SHALL also show `n_generators`, and `energy_primary` SHALL be shown only when not null. A null name SHALL display 未命名; a null capacity or operator SHALL display 未填. `capacity_source` `osm` SHALL display OSM and `taipower` SHALL display 台電官方補值. When the facility's `osm_id` appears in `official_diff.csv`, the popup SHALL show the official capacity and the difference percentage. Clicking a line SHALL open a popup with kind, maximum voltage (未填 when null), `voltage_raw`, `location` when not null, and an OSM link. All text from the data SHALL be HTML-escaped. A popup SHALL NOT display the literal text `null` or `undefined`.

#### Scenario: Missing values in popup

- **WHEN** a facility has `name` null, `capacity_mw` null and `operator` null
- **THEN** its popup shows 未命名, 未填 for capacity and 未填 for operator

#### Scenario: Capacity difference

##### Example: official difference

- **GIVEN** `official_diff.csv` has `ipp:嘉惠,w507020797,670.0,1210.0,0.446`
- **WHEN** the user clicks facility `w507020797`
- **THEN** the popup shows 台電官方容量 1,210 MW and 差 44.6%

#### Scenario: Escaping

- **WHEN** a facility name is `<b>x</b>`
- **THEN** the popup shows the literal text `<b>x</b>` rather than bold text

### Requirement: Statistics panel

The page SHALL show the snapshot time from `stats.snapshot`, the currently visible facility count and line count each with its total, the missing-capacity and missing-voltage totals, and the count of official plants without an OSM match from `stats.official.unmatched.no_osm`. Visible counts SHALL be computed from individual features passing the filters, not from rendered cluster markers, and SHALL update whenever a filter changes.

#### Scenario: Counts follow filters

- **WHEN** all energies are checked except wind, and gap mode is off
- **THEN** the visible facility count equals 1,577 minus the facilities whose `energy_sources` is exactly `["wind"]`

### Requirement: Legend and footer

Filters and legend SHALL be one panel: each checkbox shows its colour or line style. The panel SHALL list, in order, the voltage filter, the data gap toggle, the energy filter, and then the statistics. Within the statistics, the visible line count SHALL come before the visible facility count under a label stating that these numbers change with the filters, and the fixed totals (missing voltage, missing capacity, official plants without an OSM match) SHALL be grouped separately under a label stating that they cover all data. The legend SHALL state that symbol size does not represent capacity and line width does not represent power flow. The footer SHALL show: data © OpenStreetMap contributors under ODbL 1.0; Taipower and national county boundary data under 政府資料開放授權條款第1版; the OSM snapshot time; and a statement that the map is not a real-time supply map and that a facility's presence does not mean it is operating.

#### Scenario: Statistics below the filters

- **WHEN** the page loads on a desktop viewport
- **THEN** the statistics block appears after the energy filter and before the footer, the visible counts are labelled as changing with the filters, and the three fixed totals are labelled as covering all data

#### Scenario: Footer content

- **WHEN** the page loads with `stats.snapshot` `2026-11-11T21:22:47Z`
- **THEN** the footer shows that snapshot time, both licences, and the not-real-time statement

### Requirement: Responsive layout

At viewport widths below 768 px, the side panel SHALL become a bottom drawer that is collapsed by default and can be expanded and collapsed by the user; the map SHALL remain operable while the drawer is collapsed. At 768 px and above, the side panel SHALL be shown beside the map.

#### Scenario: Mobile drawer

- **WHEN** the page is opened at 390×844
- **THEN** the filters are in a collapsed bottom drawer and tapping its handle expands it
