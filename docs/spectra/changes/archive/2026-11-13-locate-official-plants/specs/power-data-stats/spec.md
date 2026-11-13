## ADDED Requirements

### Requirement: Located official plant count

The `official` object in `stats.json` SHALL include `located`, the number of features in `official_points.geojson`. The terminal summary SHALL print it next to the unmatched counts. Other fields of `official` SHALL keep their values.

#### Scenario: Located count

- **WHEN** `official_points.geojson` has 30 features
- **THEN** `stats.official.located` is 30
