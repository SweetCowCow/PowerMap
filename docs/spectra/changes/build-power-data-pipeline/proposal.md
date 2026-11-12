## Why

想重現 GEOMNI〈電從哪裡來？台灣電力的空間骨架〉的台灣電力地圖，第一步需要一份可重跑、可檢查的資料：從 OpenStreetMap 快照取出發電設施與電力線，清理、分類、去重，並誠實標出缺值。後續的官方資料交叉驗證與互動網頁都建立在這份資料之上，所以先把資料管線做對。

需求來源：`taiwan-power-map-plan.md` 第 1–5、8、9 節，以及 2026-11-12 對話中的決定（多能源標為 mixed、預留資料來源欄位、先排除金門馬祖澎湖）。

整體路線分三個 change：

1. **本 change**：OSM 資料管線（只用 OSM）
2. 下一個 change：官方資料（台電、能源署等）取得與交叉驗證，涵蓋需求文件第 6 節並擴充為雙向比對與總量比對
3. 再下一個 change：Leaflet 互動網頁（需求文件第 7 節）

## What Changes

- 新增 Python 專案骨架（`pyproject.toml`、`Makefile`、`scripts/`、`powermap/` 套件、`tests/`），以 `make data` 一鍵從零產出資料
- 下載 Geofabrik 台灣 OSM 快照，並記錄快照時間
- 濾出 `power=plant|generator|line|minor_line|cable` 圖徵並匯出為逐行 GeoJSON
- 範圍限定台灣本島與鄰近島嶼：完全不觸及本島範圍框的圖徵（金門、馬祖、澎湖等）排除，跨界線（如台澎海纜）整條保留；排除數量記入摘要與統計
- 抽取後印出各類數量、幾何類型分布、多能源筆數、各離島排除數量，供人工確認
- 能源分類、容量解析、電壓解析與電壓分級的解析器，附單元測試；多種能源並列時標為 `mixed` 並以 `energy_sources` 保留全部來源，不替設施決定主要能源
- 設施整理：幾何轉點、generator 歸併到所屬 plant、屋頂型太陽能排除、同名近距離重複合併，合併紀錄寫入 `dedup_log.csv`
- 電力線整理：電壓欄位、分級、幾何簡化與座標位數縮減
- 屬性值標記資料來源（本 change 一律為 `osm`），為下一個 change 的官方資料補值預留欄位
- 輸出 `data/processed/plants.geojson`、`data/processed/lines.geojson`、`data/processed/stats.json`
- 所有缺值以 `null` 表示，不補零、不補線

## Non-Goals

範圍排除與替代方案的取捨記錄在 design.md 的 Goals / Non-Goals 一節。

## Capabilities

### New Capabilities

- `osm-power-extraction`: 下載台灣 OSM 快照、記錄快照時間、濾出電力圖徵、套用本島範圍篩選並匯出逐行 GeoJSON，提供數量、幾何分布、多能源與排除數量摘要
- `power-facility-dataset`: 由 plant / generator 產出設施點資料集，含能源分類（含 mixed）、容量解析、資料來源標記、歸併與去重規則及其紀錄
- `power-line-dataset`: 由 line / minor_line / cable 產出電力線資料集，含電壓解析、電壓分級、資料來源標記與幾何簡化
- `power-data-stats`: 彙整設施與電力線資料集，產出含快照時間、數量、缺值、分類與排除統計的 `stats.json`

### Modified Capabilities

（無）

## Impact

- 新增檔案：pyproject.toml、Makefile、README.md、scripts/、powermap/、tests/、data/processed/
- 修改檔案：.gitignore（排除 data/raw/ 與 data/interim/）
- 新增依賴：uv（安裝到 ~/.local/bin）、Python 3.11+、osmium（pyosmium）、geopandas、shapely、pandas、pyogrio、pytest
- 外部資料：Geofabrik 台灣快照（ODbL 1.0；檔案大小為估計值約數百 MB，未量測，下載後以 ls -lh 確認；不進 git）
