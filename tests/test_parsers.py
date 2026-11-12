"""Parameterized tests mirroring every example row in the specs."""

import pytest

from powermap.parsers import (
    classify_energy,
    classify_voltage,
    parse_capacity_mw,
    parse_voltage_max_kv,
)

# power-facility-dataset / Energy classification / Example: energy categories
ENERGY_CASES = [
    ("solar", "solar", ["solar"]),
    ("Wind", "wind", ["wind"]),
    ("coal;gas", "mixed", ["coal", "gas"]),
    ("gas;coal", "mixed", ["gas", "coal"]),
    ("solar;solar", "solar", ["solar"]),
    (" ;nuclear", "nuclear", ["nuclear"]),
    ("diesel", "other", ["other"]),
    ("oil;diesel", "other", ["other"]),
    ("coal;biomass", "mixed", ["coal", "other"]),
    ("battery", "other", ["other"]),
    (None, "unknown", []),
    ("", "unknown", []),
]


@pytest.mark.parametrize("tag,energy,sources", ENERGY_CASES)
def test_classify_energy(tag, energy, sources):
    assert classify_energy(tag) == (energy, sources)


# power-facility-dataset / Capacity parsing / Example: capacity parsing
CAPACITY_CASES = [
    ("550 MW", 550),
    ("1.2 GW", 1200),
    ("499 kW", 0.499),
    ("4500 kWp", 4.5),
    ("2MWp", 2),
    ("500", 500),
    ("yes", None),
    ("1,5 MW", None),
    ("about 3 MW", None),
    (None, None),
]


@pytest.mark.parametrize("tag,expected", CAPACITY_CASES)
def test_parse_capacity_mw(tag, expected):
    result = parse_capacity_mw(tag)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


@pytest.mark.parametrize("tag", ["-5 MW", "5 TW", "5 W", "5 w"])
def test_parse_capacity_edge_units(tag):
    if tag in ("5 W", "5 w"):
        assert parse_capacity_mw(tag) == pytest.approx(5e-6)
    else:
        assert parse_capacity_mw(tag) is None


# power-line-dataset / Voltage parsing / Example: voltage parsing
VOLTAGE_CASES = [
    ("345000", 345),
    ("345000;161000", 345),
    ("161000;69000;11400", 161),
    ("11400", 11.4),
    ("161000;unknown", 161),
    ("high", None),
    (None, None),
]


@pytest.mark.parametrize("tag,expected", VOLTAGE_CASES)
def test_parse_voltage_max_kv(tag, expected):
    result = parse_voltage_max_kv(tag)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


# power-line-dataset / Voltage classification / Example: class boundaries
CLASS_CASES = [
    (345, "ehv"),
    (344.9, "hv"),
    (161, "hv"),
    (160.9, "mv"),
    (69, "mv"),
    (68.9, "lv"),
    (11.4, "lv"),
    (None, "missing"),
]


@pytest.mark.parametrize("kv,expected", CLASS_CASES)
def test_classify_voltage(kv, expected):
    assert classify_voltage(kv) == expected
