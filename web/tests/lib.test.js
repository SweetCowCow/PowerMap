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
  facilityGroupKey,
  facilityPopupHtml,
  facilityStyle,
  facilityVisible,
  initialFilters,
  formatCapacity,
  linePopupHtml,
  lineVisible,
  mainPolygonBounds,
  nominatimUrl,
  parseDiffCsv,
  reserveSlot,
  searchFacilities,
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

// --- Location tools ------------------------------------------------------------------

const named = (name) => ({ properties: { name } });

test("searchFacilities matches names (spec example table)", () => {
  const features = [named("大潭發電廠"), named("大潭風力"), named(null), named("Taichung Power Plant"), named("台中電廠")];
  assert.deepEqual(searchFacilities(features, "大潭").map((f) => f.properties.name), ["大潭發電廠", "大潭風力"]);
  assert.deepEqual(searchFacilities(features, "taichung").map((f) => f.properties.name), ["Taichung Power Plant"]);
  assert.deepEqual(searchFacilities(features, ""), []);
  assert.deepEqual(searchFacilities(features, "   "), []);
});

test("searchFacilities respects the limit", () => {
  const features = Array.from({ length: 20 }, (_, i) => named(`光電 ${i}`));
  assert.equal(searchFacilities(features, "光電").length, 8);
  assert.equal(searchFacilities(features, "光電", 3).length, 3);
});

test("nominatimUrl restricts to Taiwan and encodes the query", () => {
  const url = new URL(nominatimUrl(" 台北車站 & 1號 "));
  assert.equal(url.origin + url.pathname, "https://nominatim.openstreetmap.org/search");
  assert.equal(url.searchParams.get("countrycodes"), "tw");
  assert.equal(url.searchParams.get("format"), "jsonv2");
  assert.equal(url.searchParams.get("limit"), "5");
  assert.equal(url.searchParams.get("q"), "台北車站 & 1號");
  assert.ok(!nominatimUrl("a&b").includes("q=a&b"));
});

test("mainPolygonBounds ignores small far-off islands", () => {
  const square = (x, y, size) => [[[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]];
  const kaohsiung = { type: "MultiPolygon", coordinates: [square(116.7, 20.7, 0.05), square(120.2, 22.5, 0.8)] };
  assert.deepEqual(mainPolygonBounds(kaohsiung), [[22.5, 120.2], [23.3, 121]]);
  assert.deepEqual(mainPolygonBounds({ type: "Polygon", coordinates: square(121, 25, 0.1) }), [[25, 121], [25.1, 121.1]]);
});

// --- Defaults, symbols, clustering, request pacing -----------------------------------

test("initial filters: lines on, facilities off, gap mode off", () => {
  const f = initialFilters();
  assert.equal(f.energies.size, 0);
  assert.deepEqual([...f.voltages], VOLTAGE_ORDER);
  assert.equal(f.gapsOnly, false);
  assert.equal(facilityVisible({ energy_sources: ["solar"], missing_capacity: true }, f), false);
  assert.equal(facilityVisible({ energy_sources: [], missing_capacity: true }, f), false);
  assert.equal(lineVisible({ voltage_class: "missing", missing_voltage: true }, f), true);
});

test("facility symbols (spec example table)", () => {
  const solarPlant = facilityStyle({ kind: "plant", energy: "solar" });
  assert.equal(solarPlant.shape, "circle");
  assert.equal(solarPlant.fillColor, "#ffd15c");
  const windGen = facilityStyle({ kind: "generator", energy: "wind" });
  assert.equal(windGen.fillColor, "#6fe0c0");
  assert.ok(windGen.radius < solarPlant.radius, "generator radius is smaller than plant radius");
  const mixed = facilityStyle({ kind: "plant", energy: "mixed" });
  assert.equal(mixed.fillColor, "#b98ad9");
  assert.equal(mixed.color, "#ffffff");
  assert.ok(mixed.dashArray);
  const nuclear = facilityStyle({ kind: "plant", energy: "nuclear" });
  assert.equal(nuclear.shape, "diamond");
  assert.equal(nuclear.color, "#ffffff");
  assert.equal(nuclear.fillColor, "none");
  const big = facilityStyle({ kind: "plant", energy: "solar", capacity_mw: 500 });
  const small = facilityStyle({ kind: "plant", energy: "solar", capacity_mw: 1 });
  assert.equal(big.radius, small.radius, "radius never depends on capacity");
});

test("generators cluster per energy, plants never cluster", () => {
  assert.equal(facilityGroupKey({ kind: "generator", energy: "wind" }), "wind");
  assert.equal(facilityGroupKey({ kind: "generator", energy: "solar" }), "solar");
  assert.equal(facilityGroupKey({ kind: "plant", energy: "wind" }), null);
});

test("reserveSlot keeps overlapping Nominatim requests at least 1 s apart", () => {
  // Three submits at t=0, 200, 300 ms.
  let last = 0;
  const times = [];
  for (const now of [10_000, 10_200, 10_300]) {
    const slot = reserveSlot(last, now, 1000);
    last = slot.last;
    times.push(now + slot.wait);
  }
  assert.deepEqual(times, [10_000, 11_000, 12_000]);
  assert.deepEqual(reserveSlot(0, 5_000, 1000), { last: 5_000, wait: 0 });
});
