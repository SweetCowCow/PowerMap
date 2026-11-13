## Why

目前有 47 座台電官方電廠對不到 OSM，地圖上看不到它們，只能在統計數字裡看到「47」。實際檢查後發現分成兩類：
- 約 15 座風力發電站：OSM 其實已經有它們的風機，只是一支支標成無名的 generator，沒有電廠圖徵，所以當初的對照表標成「OSM 沒有」。
- 其餘約 32 座（多為變電所、淨水場、倉庫上的小型太陽光電，以及龍門、高屏）：OSM 確實沒有。

台電資料中每一座都有地址，多數到門牌號碼（2026-11-13 實測：47 座都有地址欄位）。所以可以：把風力電廠連到 OSM 的風機；其餘的依地址查出大概位置，標在地圖上，並清楚標示是估計位置。

## What Changes

- 修正 `data/official/crosswalk.csv`：風力電廠改成用 `part` 連到 OSM 上對應的風機（一座官方電廠對多個 OSM generator），離岸一期如果確認就是那個無名的 OSM plant，就改成 `same`。不需要改程式，對照表本來就支援。
- 新增人工確認的位置表 `data/official/locations.csv`：每座仍對不到 OSM 的官方電廠一列，記錄座標、精確程度（門牌、地號、村里、路段、廠區、外海描述）、查詢方法、來源和查詢日期。
- 資料管線新增 `data/processed/official_points.geojson`：把 `locations.csv` 中、對照表 relation 為 `none` 的官方電廠輸出成點，帶官方的名稱、容量、主要能源、地址和位置精確程度。
- `stats.json` 的 `official` 物件新增 `located`（有估計位置的官方電廠數）。
- 網頁新增「台電資料（估計位置）」圖層：用空心虛線圓表示，和 OSM 的實心點明確區分，Popup 寫明「位置為依地址估計，不是 OSM 資料」，並列出地址和精確程度。這個圖層跟著能源篩選走（以官方主要能源為準），另外有一個總開關。
- `make web` 多複製 `official_points.geojson`。

## Non-Goals (optional)

（見 design.md 的 Goals / Non-Goals）

## Capabilities

### New Capabilities

- `official-locations`：人工確認的官方電廠位置表，以及輸出對不到 OSM 的官方電廠點資料

### Modified Capabilities

- `power-data-stats`：`official` 物件新增 `located`
- `web-map`：新增官方估計位置圖層
- `web-map-publishing`：`make web` 多複製 `official_points.geojson`

## Impact

- 資料：`data/official/crosswalk.csv`（修改）、`data/official/locations.csv`（新增）、`data/processed/official_points.geojson`（新增）、`plants.geojson`、`unmatched.csv`、`stats.json`（因對照表修改而更新）
- 程式：新增 `powermap/official_points.py`、`tests/test_official_points.py`；修改 `powermap/stats.py`、`tests/test_stats.py`、`Makefile`、`README.md`、`web/index.html`、`web/app.js`、`web/lib.js`、`web/style.css`、`web/tests/lib.test.js`
- 外部服務：查座標時會用 OSM Nominatim 和網路搜尋查公開的機構地址；只查台電公開資料中的地址，不涉及個人資料
