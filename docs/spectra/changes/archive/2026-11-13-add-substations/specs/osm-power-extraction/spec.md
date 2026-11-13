## MODIFIED Requirements

### Requirement: Power feature extraction

The system SHALL extract nodes, ways, and relations whose `power` tag is one of `plant`, `generator`, `substation`, `line`, `minor_line`, `cable` and that pass the main island scope filter into `data/interim/power.geojsonseq`, one GeoJSON Feature per line. Each Feature SHALL carry all original OSM tags plus `osm_type` (`node`, `way`, or `relation`) and the original numeric OSM id. For `plant`, `generator` and `substation`, a closed way or a multipolygon relation SHALL be emitted as a Polygon or MultiPolygon, and a node as a Point. For `line`, `minor_line`, and `cable`, ways SHALL be emitted as LineString. Features with other `power` values, including `tower`, SHALL NOT be emitted. Adding `substation` SHALL NOT change which `plant`, `generator`, `line`, `minor_line` or `cable` Features are emitted, and SHALL NOT change the count of multi-source facilities.

#### Scenario: Closed plant way becomes a polygon

- **WHEN** a closed way is tagged `power=plant`
- **THEN** its Feature in `power.geojsonseq` has a Polygon geometry, `osm_type` `way`, and the way's original id

#### Scenario: Closed cable way stays a line

- **WHEN** a closed way is tagged `power=cable`
- **THEN** its Feature in `power.geojsonseq` has a LineString geometry

#### Scenario: Substation is extracted

- **WHEN** a closed way is tagged `power=substation` and a node is tagged `power=substation`
- **THEN** `power.geojsonseq` has a Polygon Feature for the way and a Point Feature for the node

#### Scenario: Tower is excluded

- **WHEN** a node is tagged `power=tower`
- **THEN** no Feature for it appears in `power.geojsonseq`

#### Scenario: Substation outside the main island is excluded

- **WHEN** a substation lies entirely within the Kinmen box
- **THEN** it is not emitted and the summary counts it under `kinmen` and under `power` value `substation`
