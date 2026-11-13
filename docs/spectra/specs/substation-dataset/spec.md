# substation-dataset Specification

## Purpose

Turn OSM `power=substation` features into a point dataset with parsed maximum voltage and the same voltage classes as power lines, so the web map can show where lines meet and at which voltage, keeping missing values explicit.

## Requirements

### Requirement: Substation dataset output

The system SHALL read `power.geojsonseq`, take every Feature whose `power` tag is `substation`, and write `data/processed/substations.geojson` as a FeatureCollection of Points in EPSG:4326 with coordinates rounded to 5 decimal places. A Polygon or MultiPolygon SHALL be converted with `representative_point()`; a Point SHALL be kept. Each Feature SHALL have, in order, the properties `osm_id`, `osm_url`, `name`, `operator`, `substation`, `voltage_max_kv`, `voltage_raw`, `voltage_class`, `voltage_source`, `missing_voltage`, `geom_src`. Features SHALL be sorted by OSM type (node, way, relation) and then by numeric OSM id. Substations SHALL NOT be deduplicated or merged. When there is no substation, the output SHALL be an empty FeatureCollection.

#### Scenario: Polygon substation becomes a point

- **WHEN** a closed way 42 is tagged `power=substation`, `name=龍潭變電所`, `voltage=345000;161000`, `substation=transmission`
- **THEN** `substations.geojson` has a Point inside that polygon with `osm_id` `w42`, `name` `龍潭變電所`, `substation` `transmission`, `voltage_max_kv` 345, `voltage_class` `ehv`, `voltage_source` `osm`, `missing_voltage` false, and `geom_src` `Polygon`

#### Scenario: Missing values stay null

##### Example: missing tags

| Tags | name | operator | substation | voltage_max_kv | voltage_class | voltage_source | missing_voltage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `power=substation` only | null | null | null | null | missing | null | true |
| `name:zh=中寮`, `voltage=high` | 中寮 | null | null | null | missing | null | true |
| `voltage=69000`, `operator=台灣電力公司` | null | 台灣電力公司 | null | 69 | mv | osm | false |

#### Scenario: No substations

- **WHEN** `power.geojsonseq` contains no substation
- **THEN** `substations.geojson` is a FeatureCollection with an empty `features` array

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