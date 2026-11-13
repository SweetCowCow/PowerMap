// Unit tests for web/lib.js (spec: web-map). Run with `make test-web`.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ENERGY_COLORS,
  ENERGY_ORDER,
  VOLTAGE_ORDER,
  VOLTAGE_STYLES,
  countVisible,
  escapeHtml,
  facilityPopupHtml,
  facilityVisible,
  formatCapacity,
  linePopupHtml,
  lineVisible,
  parseDiffCsv,
} from "../lib.js";

const filters = (energies, voltages = VOLTAGE_ORDER, gapsOnly = false) => ({
  energies: new Set(energies),
  voltages: new Set(voltages),
  gapsOnly,
});

// --- Energy filter ---------------------------------------------------------------

test("energy filter follows energy_sources (spec example table)", () => {
  const cases = [
    [["coal", "gas"], ["gas"], true],
    [["coal", "gas"], ["solar"], false],
    [[], ["unknown"], true],
    [[], ["solar", "wind"], false],
    [["wind"], [], false],
  ];
  for (const [sources, checked, expected] of cases) {
    const props = { energy_sources: sources, missing_capacity: false };
    assert.equal(facilityVisible(props, filters(checked)), expected, `${sources} with ${checked}`);
  }
});

test("there are nine energy checkboxes and no mixed checkbox", () => {
  assert.equal(ENERGY_ORDER.length, 9);
  assert.ok(!ENERGY_ORDER.includes("mixed"));
});

test("plan colours", () => {
  assert.equal(ENERGY_COLORS.solar, "#ffd15c");
  assert.equal(ENERGY_COLORS.wind, "#6fe0c0");
  assert.equal(ENERGY_COLORS.mixed, ENERGY_COLORS.other);
  assert.equal(VOLTAGE_STYLES.ehv.color, "#f0b85a");
  assert.equal(VOLTAGE_STYLES.missing.color, "#b58aa8");
  assert.ok(VOLTAGE_STYLES.missing.dashArray);
  for (const cls of ["ehv", "hv", "mv", "lv"]) assert.equal(VOLTAGE_STYLES[cls].dashArray, null);
});

// --- Voltage filter and gap mode -------------------------------------------------

test("voltage filter shows a line exactly when its class is checked", () => {
  const all = filters(ENERGY_ORDER);
  const noMissing = filters(ENERGY_ORDER, ["ehv", "hv", "mv", "lv"]);
  assert.equal(lineVisible({ voltage_class: "missing", missing_voltage: true }, all), true);
  assert.equal(lineVisible({ voltage_class: "missing", missing_voltage: true }, noMissing), false);
  assert.equal(lineVisible({ voltage_class: "ehv", missing_voltage: false }, noMissing), true);
});

test("gap mode intersects filters (spec example table)", () => {
  const solar = (missing) => ({ energy_sources: ["solar"], missing_capacity: missing });
  assert.equal(facilityVisible(solar(true), filters(["solar"], VOLTAGE_ORDER, true)), true);
  assert.equal(facilityVisible(solar(false), filters(["solar"], VOLTAGE_ORDER, true)), false);
  assert.equal(facilityVisible(solar(true), filters(["wind"], VOLTAGE_ORDER, true)), false);
  assert.equal(lineVisible({ voltage_class: "missing", missing_voltage: true }, filters([], ["missing"], true)), true);
  assert.equal(lineVisible({ voltage_class: "ehv", missing_voltage: false }, filters([], ["ehv"], true)), false);
});

test("countVisible counts individual features", () => {
  const features = [
    { properties: { energy_sources: ["wind"], missing_capacity: true } },
    { properties: { energy_sources: ["solar", "wind"], missing_capacity: true } },
    { properties: { energy_sources: ["solar"], missing_capacity: false } },
  ];
  const noWind = filters(ENERGY_ORDER.filter((e) => e !== "wind"));
  assert.equal(countVisible(features, (p) => facilityVisible(p, noWind)), 2);
});

// --- Popups ------------------------------------------------------------------------

const base = {
  osm_id: "w1",
  osm_url: "https://www.openstreetmap.org/way/1",
  kind: "plant",
  name: null,
  operator: null,
  energy: "solar",
  energy_sources: ["solar"],
  capacity_mw: null,
  capacity_source: null,
  n_generators: 0,
  energy_primary: null,
};

test("missing values show 未命名 and 未填, never null/undefined", () => {
  const html = facilityPopupHtml(base, undefined);
  assert.match(html, /未命名/);
  assert.match(html, /<th>容量<\/th><td>未填<\/td>/);
  assert.match(html, /<th>營運者<\/th><td>未填<\/td>/);
  assert.doesNotMatch(html, /null|undefined/);
  const lineHtml = linePopupHtml({ kind: "line", voltage_max_kv: null, voltage_raw: null, voltage_class: "missing",
    location: null, osm_url: "https://www.openstreetmap.org/way/2" });
  assert.match(lineHtml, /<th>最高電壓<\/th><td>未填<\/td>/);
  assert.doesNotMatch(lineHtml, /null|undefined/);
});

test("capacity source and official difference (嘉惠)", () => {
  const diff = parseDiffCsv(
    "official_id,osm_id,osm_capacity_mw,official_capacity_mw,diff_ratio\nipp:嘉惠,w507020797,670.0,1210.0,0.446\n",
  );
  const props = { ...base, osm_id: "w507020797", name: "嘉惠電廠", energy: "gas", energy_sources: ["gas"],
    capacity_mw: 670, capacity_source: "osm", energy_primary: "gas" };
  const html = facilityPopupHtml(props, diff.get("w507020797"));
  assert.match(html, /台電官方容量 1,210 MW/);
  assert.match(html, /差 44\.6%/);
  assert.match(html, /<th>容量來源<\/th><td>OSM<\/td>/);
  assert.match(html, /官方主要能源/);
  assert.match(facilityPopupHtml({ ...props, capacity_source: "taipower" }), /台電官方補值/);
});

test("mixed energy lists its sources", () => {
  const html = facilityPopupHtml({ ...base, energy: "mixed", energy_sources: ["coal", "gas"] });
  assert.match(html, /多種能源（燃煤、燃氣）/);
});

test("text from data is HTML-escaped", () => {
  const html = facilityPopupHtml({ ...base, name: "<b>x</b>", operator: "a & b" });
  assert.match(html, /&lt;b&gt;x&lt;\/b&gt;/);
  assert.doesNotMatch(html, /<b>x<\/b>/);
  assert.match(html, /a &amp; b/);
  assert.equal(escapeHtml(`"'`), "&quot;&#39;");
});

test("line popup shows voltage, raw string and location", () => {
  const html = linePopupHtml({ kind: "cable", voltage_max_kv: 345, voltage_raw: "345000;161000",
    voltage_class: "ehv", location: "underground", osm_url: "https://www.openstreetmap.org/way/3" });
  assert.match(html, /345 kV/);
  assert.match(html, /<code>345000;161000<\/code>/);
  assert.match(html, /地下/);
  assert.match(html, /電纜/);
});

// --- Parsing and formatting --------------------------------------------------------

test("parseDiffCsv handles BOM, CRLF, quotes and blank lines", () => {
  const text = "﻿official_id,osm_id,osm_capacity_mw,official_capacity_mw,diff_ratio\r\n"
    + "\"ipp:豐德, 一期\",w151212447,980.0,2113.8,0.536\r\n\r\n";
  const map = parseDiffCsv(text);
  assert.equal(map.size, 1);
  const row = map.get("w151212447");
  assert.equal(row.official_id, "ipp:豐德, 一期");
  assert.equal(row.official_capacity_mw, 2113.8);
  assert.equal(row.diff_ratio, 0.536);
  assert.equal(parseDiffCsv("").size, 0);
});

test("formatCapacity", () => {
  assert.equal(formatCapacity(null), "未填");
  assert.equal(formatCapacity(undefined), "未填");
  assert.equal(formatCapacity(1210), "1,210 MW");
  assert.equal(formatCapacity(4984.2), "4,984.2 MW");
  assert.equal(formatCapacity(0.04), "0.04 MW");
});
