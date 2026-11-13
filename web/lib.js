// Pure helpers for the web map: styles, filters, popup content, counting.
// No DOM or Leaflet access, so the same module loads in the browser and in `node --test`.

/** Energy checkboxes, in display order. `mixed` is a symbol style, not a filter. */
export const ENERGY_ORDER = ["solar", "wind", "hydro", "gas", "coal", "nuclear", "geothermal", "other", "unknown"];

export const ENERGY_LABELS = {
  solar: "太陽能",
  wind: "風力",
  hydro: "水力",
  gas: "燃氣",
  coal: "燃煤",
  nuclear: "核能",
  geothermal: "地熱",
  other: "其他",
  mixed: "多種能源",
  unknown: "未填能源",
};

export const ENERGY_COLORS = {
  solar: "#ffd15c",
  wind: "#6fe0c0",
  hydro: "#5aa9ff",
  gas: "#ff9a6b",
  coal: "#e0605f",
  nuclear: "#ffffff",
  geothermal: "#d98a3d",
  other: "#b98ad9",
  mixed: "#b98ad9",
  unknown: "#8a94a0",
};

/** Voltage checkboxes, in display order. Line width is constant on purpose. */
export const VOLTAGE_ORDER = ["ehv", "hv", "mv", "lv", "missing"];

export const VOLTAGE_STYLES = {
  ehv: { color: "#f0b85a", dashArray: null, label: "≥ 345 kV" },
  hv: { color: "#6cc4e8", dashArray: null, label: "161–345 kV" },
  mv: { color: "#4a7f9c", dashArray: null, label: "69–161 kV" },
  lv: { color: "#3d5566", dashArray: null, label: "< 69 kV" },
  missing: { color: "#b58aa8", dashArray: "4 4", label: "缺電壓" },
};

const KIND_LABELS = { plant: "電廠", generator: "發電機", line: "輸電線", minor_line: "次級線", cable: "電纜" };
const LOCATION_LABELS = { underground: "地下", underwater: "海底", overhead: "架空", underwater_cable: "海底" };
const CAPACITY_SOURCE_LABELS = { osm: "OSM", taipower: "台電官方補值" };
const MISSING = "未填";

/**
 * A facility is visible when one of its energy sources is checked (an empty source list
 * counts as `unknown`), and, in gap mode, when its capacity is missing.
 * @param {object} props facility properties
 * @param {{energies: Set<string>, voltages: Set<string>, gapsOnly: boolean}} filters
 */
export function facilityVisible(props, filters) {
  if (filters.gapsOnly && props.missing_capacity !== true) return false;
  const sources = props.energy_sources ?? [];
  if (sources.length === 0) return filters.energies.has("unknown");
  return sources.some((s) => filters.energies.has(s));
}

/** A line is visible when its voltage class is checked and, in gap mode, its voltage is missing. */
export function lineVisible(props, filters) {
  if (filters.gapsOnly && props.missing_voltage !== true) return false;
  return filters.voltages.has(props.voltage_class);
}

/** Count GeoJSON features whose properties pass `predicate`. */
export function countVisible(features, predicate) {
  let n = 0;
  for (const f of features) if (predicate(f.properties)) n += 1;
  return n;
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value, maxDigits = 2) {
  return value.toLocaleString("en-US", { maximumFractionDigits: maxDigits });
}

/** `1210` → `1,210 MW`; null → `未填`. */
export function formatCapacity(mw) {
  if (mw === null || mw === undefined || Number.isNaN(mw)) return MISSING;
  return `${formatNumber(mw)} MW`;
}

/** Split one CSV line, honouring double quotes. */
function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

/**
 * Parse `official_diff.csv` into a Map keyed by `osm_id`.
 * @returns {Map<string, {official_id: string, osm_capacity_mw: number, official_capacity_mw: number, diff_ratio: number}>}
 */
export function parseDiffCsv(text) {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.trim() !== "");
  const result = new Map();
  if (lines.length === 0) return result;
  const header = splitCsvLine(lines[0]);
  for (const line of lines.slice(1)) {
    const cells = splitCsvLine(line);
    const row = Object.fromEntries(header.map((h, i) => [h, cells[i] ?? ""]));
    if (!row.osm_id) continue;
    result.set(row.osm_id, {
      official_id: row.official_id,
      osm_capacity_mw: Number(row.osm_capacity_mw),
      official_capacity_mw: Number(row.official_capacity_mw),
      diff_ratio: Number(row.diff_ratio),
    });
  }
  return result;
}

function energyText(props) {
  if (props.energy === "mixed") {
    const parts = (props.energy_sources ?? []).map((s) => ENERGY_LABELS[s] ?? s);
    return `${ENERGY_LABELS.mixed}（${parts.join("、")}）`;
  }
  return ENERGY_LABELS[props.energy] ?? props.energy ?? MISSING;
}

function row(label, valueHtml) {
  return `<tr><th>${escapeHtml(label)}</th><td>${valueHtml}</td></tr>`;
}

function osmLink(url) {
  if (!url) return "";
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">在 OpenStreetMap 查看</a>`;
}

/**
 * Popup HTML for a facility.
 * @param {object} props facility properties
 * @param {{official_capacity_mw: number, diff_ratio: number} | undefined} diff row from official_diff.csv
 */
export function facilityPopupHtml(props, diff) {
  const name = props.name ?? "未命名";
  const rows = [
    row("種類", escapeHtml(KIND_LABELS[props.kind] ?? props.kind ?? MISSING)),
    row("能源", escapeHtml(energyText(props))),
    row("容量", escapeHtml(formatCapacity(props.capacity_mw))),
  ];
  if (props.capacity_mw !== null && props.capacity_mw !== undefined && props.capacity_source) {
    rows.push(row("容量來源", escapeHtml(CAPACITY_SOURCE_LABELS[props.capacity_source] ?? props.capacity_source)));
  }
  if (diff) {
    const pct = formatNumber(diff.diff_ratio * 100, 1);
    rows.push(row("官方比對", escapeHtml(`台電官方容量 ${formatCapacity(diff.official_capacity_mw)}，與 OSM 差 ${pct}%`)));
  }
  if (props.energy_primary) {
    rows.push(row("官方主要能源", escapeHtml(ENERGY_LABELS[props.energy_primary] ?? props.energy_primary)));
  }
  rows.push(row("營運者", escapeHtml(props.operator ?? MISSING)));
  if (props.kind === "plant") {
    rows.push(row("內含發電機", escapeHtml(`${props.n_generators ?? 0} 支`)));
  }
  return `<div class="popup"><h3>${escapeHtml(name)}</h3><table>${rows.join("")}</table>${osmLink(props.osm_url)}</div>`;
}

/** Popup HTML for a power line. */
export function linePopupHtml(props) {
  const kv = props.voltage_max_kv;
  const rows = [
    row("種類", escapeHtml(KIND_LABELS[props.kind] ?? props.kind ?? MISSING)),
    row("最高電壓", escapeHtml(kv === null || kv === undefined ? MISSING : `${formatNumber(kv)} kV`)),
    row("原始 voltage", props.voltage_raw ? `<code>${escapeHtml(props.voltage_raw)}</code>` : MISSING),
  ];
  if (props.location) {
    rows.push(row("位置", escapeHtml(LOCATION_LABELS[props.location] ?? props.location)));
  }
  const title = VOLTAGE_STYLES[props.voltage_class]?.label ?? "電力線";
  return `<div class="popup"><h3>${escapeHtml(title)}</h3><table>${rows.join("")}</table>${osmLink(props.osm_url)}</div>`;
}

/**
 * Facilities whose name contains `query` (case-insensitive), skipping unnamed ones.
 * @returns {object[]} up to `limit` GeoJSON features
 */
export function searchFacilities(features, query, limit = 8) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const out = [];
  for (const f of features) {
    const name = f.properties.name;
    if (name && name.toLowerCase().includes(q)) {
      out.push(f);
      if (out.length >= limit) break;
    }
  }
  return out;
}

/** Nominatim search URL restricted to Taiwan (usage policy: only on explicit submit). */
export function nominatimUrl(query) {
  const params = new URLSearchParams({
    format: "jsonv2",
    countrycodes: "tw",
    "accept-language": "zh-TW",
    limit: "5",
    q: query.trim(),
  });
  return `https://nominatim.openstreetmap.org/search?${params}`;
}

/** Planar area of a lon/lat ring (shoelace); only used to compare polygon sizes. */
function ringArea(ring) {
  let sum = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    sum += (ring[j][0] - ring[i][0]) * (ring[j][1] + ring[i][1]);
  }
  return Math.abs(sum / 2);
}

/**
 * Bounds `[[south, west], [north, east]]` of the largest polygon of a (Multi)Polygon, so a county
 * jump ignores far-off islands (e.g. 高雄市 includes 東沙島 and 太平島).
 */
export function mainPolygonBounds(geometry) {
  const polygons = geometry.type === "MultiPolygon" ? geometry.coordinates : [geometry.coordinates];
  let best = polygons[0];
  for (const poly of polygons) if (ringArea(poly[0]) > ringArea(best[0])) best = poly;
  const lons = best[0].map((c) => c[0]);
  const lats = best[0].map((c) => c[1]);
  return [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
}

/**
 * Names of required files whose fetch was rejected.
 * @param {string[]} names required file names, in the same order as `settled`
 * @param {PromiseSettledResult[]} settled results of Promise.allSettled
 */
export function failedFiles(names, settled) {
  return names.filter((_, i) => settled[i]?.status !== "fulfilled");
}

/** Voltage checkbox count: lines and substations, e.g. "264 段・31 座". */
export function voltageCountLabel(lines, substations) {
  const f = (n) => (n ?? 0).toLocaleString("en-US");
  return `${f(lines)} 段・${f(substations)} 座`;
}

/** Default filter state: all voltage classes and substations on, all energies off, gap mode off (lines first). */
export function initialFilters() {
  return { energies: new Set(), voltages: new Set(VOLTAGE_ORDER), gapsOnly: false, substations: true, officialPoints: true };
}

/** Data files the page cannot render without; `official_diff.csv` is optional and loaded separately. */
export const REQUIRED_FILES = [
  "plants.geojson",
  "lines.geojson",
  "substations.geojson",
  "official_points.geojson",
  "stats.json",
  "counties.geojson",
];

// --- Substations ------------------------------------------------------------------------

export const SUBSTATION_TYPE_LABELS = {
  transmission: "輸電",
  distribution: "配電",
  minor_distribution: "小型配電",
  transition: "架空與地下轉接",
  industrial: "工業用",
  traction: "鐵路供電",
  converter: "換流",
};

/** Type label for the `substation` tag; `null` and `yes` are unknown. */
export function substationTypeLabel(value) {
  if (value === null || value === undefined || value === "yes") return MISSING;
  return SUBSTATION_TYPE_LABELS[value] ?? value;
}

/** A substation follows the substation toggle, the voltage filter and gap mode. */
export function substationVisible(props, filters) {
  if (!filters.substations) return false;
  if (filters.gapsOnly && props.missing_voltage !== true) return false;
  return filters.voltages.has(props.voltage_class);
}

/** Popup HTML for a substation. */
export function substationPopupHtml(props) {
  const kv = props.voltage_max_kv;
  const rows = [
    row("種類", escapeHtml(`變電所・${substationTypeLabel(props.substation)}`)),
    row("最高電壓", escapeHtml(kv === null || kv === undefined ? MISSING : `${formatNumber(kv)} kV`)),
    row("原始 voltage", props.voltage_raw ? `<code>${escapeHtml(props.voltage_raw)}</code>` : MISSING),
    row("營運者", escapeHtml(props.operator ?? MISSING)),
  ];
  return `<div class="popup"><h3>${escapeHtml(props.name ?? "未命名變電所")}</h3><table>${rows.join("")}</table>${osmLink(props.osm_url)}</div>`;
}

export const PLANT_RADIUS = 5;
export const GENERATOR_RADIUS = 3;

/**
 * Symbol for a facility. Radius only tells plant from generator; it never depends on capacity.
 * @returns {{shape: "circle"|"diamond", radius: number, fillColor: string, color: string, weight: number, dashArray: string|null}}
 */
export function facilityStyle(props) {
  const radius = props.kind === "plant" ? PLANT_RADIUS : GENERATOR_RADIUS;
  if (props.energy === "nuclear") {
    return { shape: "diamond", radius, fillColor: "none", color: "#ffffff", weight: 2, dashArray: null };
  }
  const mixed = props.energy === "mixed";
  return {
    shape: "circle",
    radius,
    fillColor: ENERGY_COLORS[props.energy] ?? ENERGY_COLORS.unknown,
    color: mixed ? "#ffffff" : "#0b1826",
    weight: mixed ? 1.5 : 0.8,
    dashArray: mixed ? "2 2" : null,
  };
}

/** Cluster group key: generators cluster per energy; plants never cluster (null). */
export function facilityGroupKey(props) {
  return props.kind === "generator" ? props.energy : null;
}

// --- Official estimated locations -------------------------------------------------------

/** `precision` values of data/official/locations.csv, as shown in popups. */
export const PRECISION_LABELS = {
  address: "門牌",
  parcel: "地號",
  village: "村里中心",
  road: "路段",
  site: "廠區",
  offshore: "外海",
};

/**
 * Hollow dashed circle, so an estimate never looks like a filled OSM facility symbol. Radius 9 is
 * wider than a plant dot (5) and a substation square (10 px), leaving a ring to click.
 */
export function officialPointStyle(props) {
  return {
    radius: 9,
    color: ENERGY_COLORS[props.energy_primary] ?? ENERGY_COLORS.unknown,
    weight: 2,
    dashArray: "3 3",
    fill: false,
  };
}

/**
 * An official point needs the 台電資料 toggle on, gap mode off (its capacity is known) and
 * its primary energy checked (`null` counts as `unknown`).
 */
export function officialPointVisible(props, filters) {
  if (!filters.officialPoints || filters.gapsOnly) return false;
  return filters.energies.has(props.energy_primary ?? "unknown");
}

/** Popup HTML for an official point; it always says the position is an estimate. */
export function officialPointPopupHtml(props) {
  const energy = props.energy_primary ? ENERGY_LABELS[props.energy_primary] ?? props.energy_primary : MISSING;
  const rows = [
    row("容量", escapeHtml(formatCapacity(props.capacity_mw))),
    row("主要能源", escapeHtml(energy)),
    row("地址", escapeHtml(props.address ?? MISSING)),
    row("精確程度", escapeHtml(PRECISION_LABELS[props.precision] ?? props.precision ?? MISSING)),
    row("查詢日期", escapeHtml(props.checked_at ?? MISSING)),
  ];
  return `<div class="popup"><h3>${escapeHtml(props.name ?? "未命名")}</h3>`
    + '<p class="popup-note">台電資料・位置為依地址估計，不是 OSM 資料</p>'
    + `<table>${rows.join("")}</table></div>`;
}

/**
 * Reserve the next Nominatim request slot so requests stay at least `interval` ms apart,
 * even when submits overlap. Returns the new `last` value and how long to wait.
 */
export function reserveSlot(last, now, interval = 1000) {
  const at = Math.max(now, last + interval);
  return { last: at, wait: at - now };
}
