## Why

資料管線（change 1、2）已經產出 `plants.geojson`、`lines.geojson`、`stats.json`，但目前只能用程式或 GIS 軟體查看。原始計畫的最終目標是一個可篩選、可點選、看得到資料缺口的互動網頁，並且公開讓人瀏覽。

## What Changes

- 新增 `web/` 單頁 Leaflet 地圖（純 HTML/JS，以 CDN 載入 Leaflet 1.9 與 Leaflet.markercluster，不需要打包工具）：
  - 設施依能源著色，電力線依電壓分級著色，缺電壓的線畫成虛線
  - 電壓篩選、「只看資料缺口」切換、能源篩選，圖例與篩選器合一。側欄以電力線為主：電壓篩選排第一、預設全勾；能源篩選排在最後、預設全部不勾（2026-11-13 使用者回饋：主要想看各地電力線狀況）
  - 設施與線段 Popup：缺值顯示「未填」，並顯示容量來源（OSM／官方補值），以及超過門檻的官方容量差距
  - 統計面板：讀 `stats.json`，隨篩選更新目前顯示數量，並列出對不到 OSM 的官方電廠數
  - 頁尾：資料來源、快照時間、授權，以及「不是即時供電圖」的聲明
  - 手機版：側欄收合成底部抽屜
- 907 支獨立發電機依能源分組聚合。聚合點固定大小、顯示數字並保留能源顏色，zoom ≥ 12 拆開；電廠不聚合。
- 新增縣市界底圖資料：資料管線新增 `make boundaries`，下載國土測繪中心的「直轄市、縣市界線」、簡化後輸出 `data/processed/counties.geojson`。網頁預設用它當底圖，另外可切換成以 CSS 調暗的 OSM 標準圖磚（2026-11-13 使用者回饋：改用 OSM 圖磚，取代原本的 CARTO 深色圖磚）。
- 新增 `make web`（把資料複製到 `web/data/`）和網頁單元測試（`node --test`）。
- 新增 GitHub Actions：push 到 `main` 後執行 `make web`，並發佈到 GitHub Pages。
- 上線前的一次性作業：把 git 歷史和 `.openspec.yaml` 裡的公司 email 換成 GitHub noreply 信箱，再把 repo 改成 public。force push 和切換 public 前都要再向使用者確認。

## Non-Goals (optional)

（見 design.md 的 Goals / Non-Goals）

## Capabilities

### New Capabilities

- `county-boundary-dataset`：下載並簡化縣市界線，輸出網頁底圖用的 `counties.geojson`
- `web-map`：互動地圖網頁的圖層、樣式、聚合、篩選、Popup、統計面板、頁尾與響應式版面
- `web-map-publishing`：`make web` 建置靜態網站，以及用 GitHub Actions 發佈到 GitHub Pages

### Modified Capabilities

（無。網頁只讀取既有輸出，不改變資料管線的行為。）

## Impact

- 新增檔案：`web/index.html`、`web/app.js`、`web/lib.js`、`web/style.css`、`web/tests/`、`powermap/boundaries.py`、`tests/test_boundaries.py`、`.github/workflows/pages.yml`、`data/processed/counties.geojson`
- 修改：`Makefile`（新增 `boundaries`、`web`、`test-web` 目標）、`README.md`、`.gitignore`（忽略 `web/data/`）
- 新的外部依賴：Leaflet 1.9、Leaflet.markercluster（CDN）、OSM 標準圖磚 tile.openstreetmap.org（選用圖層）、data.gov.tw 縣市界資料集
- 變電所圖層不在本 change，另開 change 4。
- 一次性 repo 作業：改寫 git 歷史並 force push 到 `origin/main`（commit hash 全部改變）、repo 改成 public、啟用 GitHub Pages
