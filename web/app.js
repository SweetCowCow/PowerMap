// Web map wiring: data loading, Leaflet layers, filters, popups and the stats panel.
// Pure logic lives in lib.js (tested with `make test-web`).
import {
  ENERGY_COLORS,
  ENERGY_LABELS,
  ENERGY_ORDER,
  VOLTAGE_ORDER,
  VOLTAGE_STYLES,
  countVisible,
  escapeHtml,
  facilityPopupHtml,
  facilityVisible,
  linePopupHtml,
  lineVisible,
  parseDiffCsv,
} from "./lib.js";

/* global L */

const REQUIRED = ["plants.geojson", "lines.geojson", "stats.json", "counties.geojson"];
const MAIN_ISLAND = [[21.88, 119.95], [25.32, 122.03]];
const UNCLUSTER_ZOOM = 12;
const PLANT_RADIUS = 5;
const GENERATOR_RADIUS = 3;

const numberFormat = new Intl.NumberFormat("en-US");
const fmt = (n) => numberFormat.format(n);

async function loadData() {
  const fetchOne = async (name, kind) => {
    const res = await fetch(`data/${name}`);
    if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
    return kind === "text" ? res.text() : res.json();
  };
  const [required, diff] = await Promise.all([
    Promise.allSettled(REQUIRED.map((name) => fetchOne(name, "json"))),
    fetchOne("official_diff.csv", "text").then(parseDiffCsv, () => new Map()),
  ]);
  const failed = REQUIRED.filter((_, i) => required[i].status === "rejected");
  if (failed.length) return { failed };
  const [plants, lines, stats, counties] = required.map((r) => r.value);
  return { plants, lines, stats, counties, diff, failed: [] };
}

function showBanner(message) {
  const banner = document.getElementById("banner");
  banner.textContent = message;
  banner.hidden = false;
  document.getElementById("drawer-summary").textContent = "資料載入失敗";
}

function createMap() {
  const map = L.map("map", { preferCanvas: true, minZoom: 6, maxZoom: 18, zoomSnap: 0.5 });
  map.fitBounds(MAIN_ISLAND);
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution('電力資料 © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors');
  for (const [name, z] of [["counties", 250], ["lines", 410], ["facilities", 420]]) {
    map.createPane(name).style.zIndex = z;
  }
  return map;
}

function baseLayers(map, counties) {
  const outline = L.geoJSON(counties, {
    pane: "counties",
    interactive: false,
    style: { color: "#22384a", weight: 1, fillColor: "#142534", fillOpacity: 1 },
    attribution: "縣市界：內政部國土測繪中心",
  });
  const tiles = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd",
    maxZoom: 19,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
  });
  outline.addTo(map);
  L.control.layers({ "縣市界（離線）": outline, "深色圖磚": tiles }, null, { position: "topright" }).addTo(map);
}

function nuclearIcon() {
  return L.divIcon({
    className: "nuclear-icon",
    iconSize: [14, 14],
    html: '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">'
      + '<rect x="3" y="3" width="8" height="8" transform="rotate(45 7 7)" fill="none" stroke="#fff" stroke-width="2"/></svg>',
  });
}

function facilityLayer(feature, renderer, diff) {
  const p = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  let layer;
  if (p.energy === "nuclear") {
    layer = L.marker([lat, lon], { icon: nuclearIcon(), pane: "markerPane", keyboard: false });
  } else {
    const color = ENERGY_COLORS[p.energy] ?? ENERGY_COLORS.unknown;
    const mixed = p.energy === "mixed";
    layer = L.circleMarker([lat, lon], {
      renderer,
      radius: p.kind === "plant" ? PLANT_RADIUS : GENERATOR_RADIUS,
      color: mixed ? "#ffffff" : "#0b1826",
      weight: mixed ? 1.5 : 0.8,
      dashArray: mixed ? "2 2" : null,
      fillColor: color,
      fillOpacity: 0.95,
    });
  }
  layer.bindPopup(() => facilityPopupHtml(p, diff.get(p.osm_id)), { maxWidth: 320 });
  return layer;
}

function clusterGroup(energy) {
  const color = ENERGY_COLORS[energy] ?? ENERGY_COLORS.unknown;
  return L.markerClusterGroup({
    disableClusteringAtZoom: UNCLUSTER_ZOOM,
    maxClusterRadius: 40,
    showCoverageOnHover: false,
    spiderfyOnMaxZoom: false,
    clusterPane: "markerPane",
    iconCreateFunction: (cluster) => L.divIcon({
      className: "",
      iconSize: [28, 28],
      html: `<div class="energy-cluster" style="--cluster:${color}" title="${escapeHtml(ENERGY_LABELS[energy] ?? energy)}發電機 ${cluster.getChildCount()} 支">${cluster.getChildCount()}</div>`,
    }),
  });
}

function buildOptions(listId, order, labelFor, countFor, swatchFor) {
  const list = document.getElementById(listId);
  list.innerHTML = order.map((key) => `
    <li><label>
      <input type="checkbox" value="${key}" checked>
      ${swatchFor(key)}
      <span class="option-label">${escapeHtml(labelFor(key))}</span>
      <span class="option-count">${fmt(countFor(key))}</span>
    </label></li>`).join("");
  return list;
}

function checkedValues(list) {
  return new Set([...list.querySelectorAll("input:checked")].map((i) => i.value));
}

function setupDrawer() {
  const panel = document.getElementById("panel");
  const handle = document.getElementById("drawer-handle");
  handle.addEventListener("click", () => {
    const open = panel.classList.toggle("open");
    handle.setAttribute("aria-expanded", String(open));
  });
}

async function main() {
  setupDrawer();
  const map = createMap();
  const data = await loadData();
  if (data.failed.length) {
    showBanner(`無法載入資料檔：${data.failed.join("、")}。請確認已執行 make web，再重新整理頁面。`);
    return;
  }
  const { plants, lines, stats, counties, diff } = data;
  baseLayers(map, counties);

  // --- Layers --------------------------------------------------------------------------
  const lineRenderer = L.canvas({ pane: "lines", padding: 0.3 });
  const facilityRenderer = L.canvas({ pane: "facilities", padding: 0.3 });

  const lineItems = lines.features.map((f) => {
    const style = VOLTAGE_STYLES[f.properties.voltage_class] ?? VOLTAGE_STYLES.missing;
    const layer = L.geoJSON(f, {
      renderer: lineRenderer,
      style: { color: style.color, weight: 1.6, opacity: 0.9, dashArray: style.dashArray },
    });
    layer.bindPopup(() => linePopupHtml(f.properties), { maxWidth: 300 });
    return { props: f.properties, layer };
  });
  const lineGroup = L.layerGroup().addTo(map);

  const plantGroup = L.layerGroup().addTo(map);
  const clusters = new Map();
  const facilityItems = plants.features.map((f) => {
    const props = f.properties;
    const layer = facilityLayer(f, facilityRenderer, diff);
    let group = plantGroup;
    if (props.kind === "generator") {
      if (!clusters.has(props.energy)) clusters.set(props.energy, clusterGroup(props.energy).addTo(map));
      group = clusters.get(props.energy);
    }
    return { props, layer, group };
  });

  // --- Controls ------------------------------------------------------------------------
  const energyCount = (key) => countVisible(plants.features, (p) => (key === "unknown"
    ? (p.energy_sources ?? []).length === 0
    : (p.energy_sources ?? []).includes(key)));
  const energyList = buildOptions("energy-options", ENERGY_ORDER, (k) => ENERGY_LABELS[k], energyCount,
    (k) => (k === "nuclear"
      ? '<span class="swatch swatch-diamond" aria-hidden="true"></span>'
      : `<span class="swatch" style="--swatch:${ENERGY_COLORS[k]}" aria-hidden="true"></span>`));
  const voltageList = buildOptions("voltage-options", VOLTAGE_ORDER, (k) => VOLTAGE_STYLES[k].label,
    (k) => stats.by_voltage_class?.[k] ?? 0,
    (k) => `<span class="swatch swatch-line${VOLTAGE_STYLES[k].dashArray ? " dashed" : ""}" style="--swatch:${VOLTAGE_STYLES[k].color}" aria-hidden="true"></span>`);
  const gapsToggle = document.getElementById("gaps-only");

  document.getElementById("stat-facilities-total").textContent = `/ ${fmt(plants.features.length)}`;
  document.getElementById("stat-lines-total").textContent = `/ ${fmt(lines.features.length)}`;
  document.getElementById("stat-missing-capacity").textContent = fmt(stats.facilities_missing_capacity);
  document.getElementById("stat-missing-voltage").textContent = fmt(stats.lines_missing_voltage);
  document.getElementById("stat-unmatched").textContent = fmt(stats.official?.unmatched?.no_osm ?? 0);
  const snapshot = document.getElementById("snapshot");
  snapshot.textContent = stats.snapshot ?? "未知";
  if (stats.snapshot) snapshot.setAttribute("datetime", stats.snapshot);

  // --- Apply filters -------------------------------------------------------------------
  function apply() {
    const filters = { energies: checkedValues(energyList), voltages: checkedValues(voltageList), gapsOnly: gapsToggle.checked };

    lineGroup.clearLayers();
    let visibleLines = 0;
    for (const item of lineItems) {
      if (lineVisible(item.props, filters)) {
        lineGroup.addLayer(item.layer);
        visibleLines += 1;
      }
    }

    plantGroup.clearLayers();
    const perCluster = new Map([...clusters.keys()].map((k) => [k, []]));
    let visibleFacilities = 0;
    for (const item of facilityItems) {
      if (!facilityVisible(item.props, filters)) continue;
      visibleFacilities += 1;
      if (item.group === plantGroup) plantGroup.addLayer(item.layer);
      else perCluster.get(item.props.energy).push(item.layer);
    }
    for (const [energy, group] of clusters) {
      group.clearLayers();
      group.addLayers(perCluster.get(energy));
    }

    document.getElementById("stat-facilities").textContent = fmt(visibleFacilities);
    document.getElementById("stat-lines").textContent = fmt(visibleLines);
    document.getElementById("drawer-summary").textContent = `顯示 ${fmt(visibleFacilities)} 座設施、${fmt(visibleLines)} 段電力線`;
  }

  energyList.addEventListener("change", apply);
  voltageList.addEventListener("change", apply);
  gapsToggle.addEventListener("change", apply);
  document.querySelector("#energy-filter .bulk").addEventListener("click", (event) => {
    const mode = event.target.closest("button")?.dataset.bulk;
    if (!mode) return;
    for (const input of energyList.querySelectorAll("input")) input.checked = mode === "all";
    apply();
  });

  apply();
  // Handle for debugging in the browser console (e.g. powermap.map.setZoom(12)).
  window.powermap = { map, facilityItems, lineItems };
}

main().catch((err) => {
  console.error(err);
  showBanner(`地圖無法顯示：${err.message}`);
});
