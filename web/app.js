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
  mainPolygonBounds,
  nominatimUrl,
  parseDiffCsv,
  searchFacilities,
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
  // OSM standard tiles are light; the `osm-dim` class darkens only this tile layer (see style.css).
  const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    className: "osm-dim",
    attribution: '圖磚 © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  });
  const osmAttribution = '圖磚 © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  const osmPlain = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: osmAttribution });
  // NLSC WMTS uses {z}/{y}/{x} (row before column).
  const photo = L.tileLayer("https://wmts.nlsc.gov.tw/wmts/PHOTO2/default/GoogleMapsCompatible/{z}/{y}/{x}", {
    maxZoom: 19,
    attribution: '正射影像 © <a href="https://maps.nlsc.gov.tw/" target="_blank" rel="noopener">內政部國土測繪中心</a>',
  });
  outline.addTo(map);
  L.control.layers({
    "縣市界（離線）": outline,
    "OSM 圖磚（調暗）": tiles,
    "OSM 圖磚（原色）": osmPlain,
    "正射影像": photo,
  }, null, { position: "topright" }).addTo(map);
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

function buildOptions(listId, order, labelFor, countFor, swatchFor, checked) {
  const list = document.getElementById(listId);
  list.innerHTML = order.map((key) => `
    <li><label>
      <input type="checkbox" value="${key}"${checked ? " checked" : ""}>
      ${swatchFor(key)}
      <span class="option-label">${escapeHtml(labelFor(key))}</span>
      <span class="option-count">${fmt(countFor(key))}</span>
    </label></li>`).join("");
  return list;
}

function checkedValues(list) {
  return new Set([...list.querySelectorAll("input:checked")].map((i) => i.value));
}

const NOMINATIM_INTERVAL_MS = 1000;

/** County selector, facility-name search (local, as you type) and place search (Nominatim, on submit). */
function setupLocate(map, counties, plants, diff) {
  const root = document.getElementById("locate");
  L.DomEvent.disableClickPropagation(root);
  L.DomEvent.disableScrollPropagation(root);

  // --- County selector, north to south
  const select = document.getElementById("county-select");
  const countyBounds = counties.features
    .map((f) => ({ name: f.properties.name, bounds: L.latLngBounds(mainPolygonBounds(f.geometry)) }))
    .sort((a, b) => b.bounds.getCenter().lat - a.bounds.getCenter().lat);
  for (const c of countyBounds) select.add(new Option(c.name, c.name));
  select.addEventListener("change", () => {
    const hit = countyBounds.find((c) => c.name === select.value);
    if (hit) map.fitBounds(hit.bounds, { padding: [20, 20] });
    select.value = ""; // back to the placeholder, so the same county can be chosen again
  });

  // --- Search
  const input = document.getElementById("search-input");
  const form = document.getElementById("search-form");
  const results = document.getElementById("search-results");
  let facilityHits = [];
  let placeHits = null; // null: not searched; [] or array: Nominatim result; string: message
  let lastNominatim = 0;
  let highlight = null;

  const kindLabel = (p) => (p.kind === "plant" ? "電廠" : "發電機");
  function render() {
    const q = input.value.trim();
    if (!q) {
      results.hidden = true;
      results.innerHTML = "";
      return;
    }
    let html = '<p class="results-head">發電設施</p>';
    html += facilityHits.length
      ? `<ul>${facilityHits.map((f, i) => `<li><button type="button" data-facility="${i}">${escapeHtml(f.properties.name)}<span>${kindLabel(f.properties)}・${escapeHtml(ENERGY_LABELS[f.properties.energy] ?? "")}</span></button></li>`).join("")}</ul>`
      : '<p class="results-empty">沒有名稱相符的設施</p>';
    html += '<p class="results-head">地名或地址</p>';
    if (placeHits === null) {
      html += '<p class="results-note">按 Enter 或「搜尋地名」查詢。查詢文字會送到 OpenStreetMap Nominatim。</p>';
    } else if (typeof placeHits === "string") {
      html += `<p class="results-empty">${escapeHtml(placeHits)}</p>`;
    } else {
      html += `<ul>${placeHits.map((p, i) => `<li><button type="button" data-place="${i}">${escapeHtml(p.display_name)}</button></li>`).join("")}</ul>`
        + '<p class="results-note">地名搜尋 © OpenStreetMap contributors（Nominatim）</p>';
    }
    results.innerHTML = html;
    results.hidden = false;
  }

  input.addEventListener("input", () => {
    facilityHits = searchFacilities(plants.features, input.value);
    placeHits = null;
    render();
  });
  input.addEventListener("focus", render);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      results.hidden = true;
      input.blur();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    placeHits = "搜尋中…";
    render();
    const wait = lastNominatim + NOMINATIM_INTERVAL_MS - Date.now();
    if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    lastNominatim = Date.now();
    try {
      const res = await fetch(nominatimUrl(q), { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (input.value.trim() !== q) return; // the user has typed something else meanwhile
      placeHits = data.length ? data : `找不到「${q}」，請換個關鍵字。`;
    } catch {
      placeHits = "地名搜尋暫時無法使用，請稍後再試。";
    }
    render();
  });

  results.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.facility !== undefined) {
      const f = facilityHits[Number(button.dataset.facility)];
      const [lon, lat] = f.geometry.coordinates;
      const latlng = L.latLng(lat, lon);
      map.setView(latlng, Math.max(map.getZoom(), 15));
      if (highlight) highlight.remove();
      highlight = L.circleMarker(latlng, { radius: 14, color: "#f0b85a", weight: 2, fill: false, interactive: false }).addTo(map);
      L.popup({ maxWidth: 320 })
        .setLatLng(latlng)
        .setContent(facilityPopupHtml(f.properties, diff.get(f.properties.osm_id)))
        .on("remove", () => { if (highlight) { highlight.remove(); highlight = null; } })
        .openOn(map);
    } else if (button.dataset.place !== undefined) {
      const p = placeHits[Number(button.dataset.place)];
      const [s, n, w, e] = p.boundingbox.map(Number);
      map.fitBounds([[s, w], [n, e]], { maxZoom: 16 });
    }
    results.hidden = true;
  });
  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) results.hidden = true;
  });
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
      : `<span class="swatch" style="--swatch:${ENERGY_COLORS[k]}" aria-hidden="true"></span>`), false);
  const voltageList = buildOptions("voltage-options", VOLTAGE_ORDER, (k) => VOLTAGE_STYLES[k].label,
    (k) => stats.by_voltage_class?.[k] ?? 0,
    (k) => `<span class="swatch swatch-line${VOLTAGE_STYLES[k].dashArray ? " dashed" : ""}" style="--swatch:${VOLTAGE_STYLES[k].color}" aria-hidden="true"></span>`, true);
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
    document.getElementById("drawer-summary").textContent = `顯示 ${fmt(visibleLines)} 段電力線、${fmt(visibleFacilities)} 座設施`;
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
  setupLocate(map, counties, plants, diff);
  // Handle for debugging in the browser console (e.g. powermap.map.setZoom(12)).
  window.powermap = { map, facilityItems, lineItems };
}

main().catch((err) => {
  console.error(err);
  showBanner(`地圖無法顯示：${err.message}`);
});
