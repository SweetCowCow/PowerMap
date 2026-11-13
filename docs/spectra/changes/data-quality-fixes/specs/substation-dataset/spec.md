## MODIFIED Requirements

### Requirement: Substation dataset output

The system SHALL read `power.geojsonseq`, take every Feature whose `power` tag is `substation`, and write `data/processed/substations.geojson` as a FeatureCollection of Points in EPSG:4326 with coordinates rounded to 5 decimal places. A Polygon or MultiPolygon SHALL be converted with `representative_point()`; a Point SHALL be kept. Each Feature SHALL have, in order, the properties `osm_id`, `osm_url`, `name`, `operator`, `substation`, `voltage_max_kv`, `voltage_raw`, `voltage_class`, `voltage_source`, `missing_voltage`, `geom_src`. Features SHALL be sorted by OSM type (node, way, relation) and then by numeric OSM id. Substations SHALL NOT be merged; the only substations removed SHALL be those described in the requirement "Contained substation removal". When there is no substation, the output SHALL be an empty FeatureCollection.

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

## ADDED Requirements

### Requirement: Contained substation removal

For two substations A and B that are both Polygon or MultiPolygon, A SHALL be called contained in B when, computed in EPSG:3826, the area of A intersected with B is at least 90% of the area of A and A is smaller than B. When A is contained in B (B being the smallest substation containing A) and exactly one of A and B has a `name`, the one whose `name` is `null` SHALL be removed from `substations.geojson`, whether it is A or B; when both names are `null` or both are equal, A SHALL be removed; when both have different names, both SHALL be kept. A substation SHALL be removed at most once, and the substation kept in that pair is the one recorded as kept. Point substations SHALL never be removed or used as B. Each removed substation SHALL be written to `data/processed/substation_dedup_log.csv` with columns `action,kept_osm_id,dropped_osm_id,reason,distance_m`, `action` `substation_contained`, `reason` `unnamed` or `same_name`, and the distance in meters between the two representative points in EPSG:3826 rounded to 1 decimal; rows SHALL follow the output sort order of the dropped substation, and the file SHALL contain only the header when nothing is removed.

#### Scenario: Contained substations

##### Example: containment rules

| A (inner) | B (outer) | Share of A inside B | Result |
| --- | --- | --- | --- |
| 六家第一次配電變電所 | unnamed | 100% | B removed, reason `unnamed` |
| unnamed | 沙崙一次配電變電所 | 100% | A removed, reason `unnamed` |
| 義和開閉所 | 義和開閉所 | 100% | A removed, reason `same_name` |
| 台灣電力公司電力修護處南部分處 | 同盟變電所 | 100% | A kept |
| unnamed | 變電站 (only touching) | 0% | A kept |
| unnamed | 某變電所 | 89% | A kept |

#### Scenario: Nothing removed

- **WHEN** no substation is contained in another
- **THEN** `substation_dedup_log.csv` contains only the header row and `substations.geojson` has one point per substation
