"""Pure parsing helpers for OSM power tags.

Rules are defined in the Spectra specs of change ``build-power-data-pipeline``:
energy classification, capacity parsing, voltage parsing and voltage classes.
"""

from __future__ import annotations

import re

#: Source tokens that map to a category of the same name.
KNOWN_SOURCES = ("solar", "wind", "hydro", "gas", "coal", "nuclear", "geothermal")

#: Categories that may appear in ``energy_sources``.
SOURCE_CATEGORIES = KNOWN_SOURCES + ("other",)

#: Every possible ``energy`` value.
ENERGY_CATEGORIES = SOURCE_CATEGORIES + ("mixed", "unknown")

#: Every possible ``voltage_class`` value.
VOLTAGE_CLASSES = ("ehv", "hv", "mv", "lv", "missing")

_CAPACITY_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-z]*)\s*$", re.IGNORECASE)
_CAPACITY_UNIT_TO_MW = {
    "": 1.0,  # unit-less numbers are treated as MW (user decision 2026-11-12)
    "w": 1e-6,
    "kw": 1e-3,
    "kwp": 1e-3,
    "mw": 1.0,
    "mwp": 1.0,
    "gw": 1e3,
}
_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")


def _split_tokens(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [t.strip() for t in raw.split(";") if t.strip()]


def classify_energy(source: str | None) -> tuple[str, list[str]]:
    """Return ``(energy, energy_sources)`` for a ``*:source`` tag value.

    Multiple distinct categories yield ``mixed``; no primary source is chosen.
    """
    sources: list[str] = []
    for token in _split_tokens(source.lower() if source is not None else None):
        category = token if token in KNOWN_SOURCES else "other"
        if category not in sources:
            sources.append(category)
    if not sources:
        return "unknown", []
    if len(sources) == 1:
        return sources[0], sources
    return "mixed", sources


def parse_capacity_mw(raw: str | None) -> float | None:
    """Parse an ``*:output:electricity`` value into megawatts, or ``None``."""
    if raw is None:
        return None
    match = _CAPACITY_RE.match(raw)
    if not match:
        return None
    number, unit = match.groups()
    factor = _CAPACITY_UNIT_TO_MW.get(unit.lower())
    if factor is None:
        return None
    return round(float(number) * factor, 6)


def parse_voltage_max_kv(raw: str | None) -> float | None:
    """Return the highest numeric value of a ``voltage`` tag in kV, or ``None``."""
    values = [float(t) for t in _split_tokens(raw) if _NUMBER_RE.match(t)]
    if not values:
        return None
    return round(max(values) / 1000, 6)


def classify_voltage(kv: float | None) -> str:
    """Map a maximum voltage in kV to its voltage class."""
    if kv is None:
        return "missing"
    if kv >= 345:
        return "ehv"
    if kv >= 161:
        return "hv"
    if kv >= 69:
        return "mv"
    return "lv"
