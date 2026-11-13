## ADDED Requirements

### Requirement: Substation statistics

The system SHALL add to `stats.json`: `substations` (feature count of `substations.geojson`), `substations_missing_voltage`, and `substations_by_voltage_class` (an object with all five voltage classes `ehv`, `hv`, `mv`, `lv`, `missing` as keys, 0 when absent). The sum of `substations_by_voltage_class` SHALL equal `substations`. The terminal summary SHALL also print the substation count and the substation missing-voltage count. Existing fields of `stats.json` SHALL keep their values.

#### Scenario: Substation counts

##### Example: three substations

- **GIVEN** `substations.geojson` has three substations with `voltage_class` `ehv`, `missing`, `missing`
- **WHEN** `stats.json` is generated
- **THEN** `substations` is 3, `substations_missing_voltage` is 2, and `substations_by_voltage_class` is `{"ehv": 1, "hv": 0, "mv": 0, "lv": 0, "missing": 2}`

#### Scenario: No substations

- **WHEN** `substations.geojson` has no features
- **THEN** `substations` is 0 and every value in `substations_by_voltage_class` is 0
