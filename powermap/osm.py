"""OSM identifiers, power tag values and tag text helpers shared by all steps."""

from __future__ import annotations

POWER_VALUES = ("plant", "generator", "substation", "line", "minor_line", "cable")
FACILITY_VALUES = ("plant", "generator")
# Values whose closed ways and multipolygon relations are assembled into areas.
AREA_VALUES = ("plant", "generator", "substation")
LINE_VALUES = ("line", "minor_line", "cable")

_PREFIX = {"node": "n", "way": "w", "relation": "r"}
_URL = "https://www.openstreetmap.org/{type}/{id}"


def osm_ref(osm_type: str, osm_id: int) -> str:
    """Return the short id used in outputs and reports, e.g. ``w123``."""
    return f"{_PREFIX[osm_type]}{osm_id}"


def osm_url(osm_type: str, osm_id: int) -> str:
    return _URL.format(type=osm_type, id=osm_id)


def tag_text(value: str | None) -> str | None:
    """Trimmed tag text; missing or empty values become ``None``."""
    if value is None:
        return None
    value = value.strip()
    return value or None
