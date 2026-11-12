# PowerMap — 台灣電力地圖資料管線

從 OpenStreetMap（OSM）台灣快照取出發電設施與電力線，整理成可重跑、可檢查的 GeoJSON。這是台灣電力地圖專案的第一階段：

1. **OSM 資料管線**（本 repo 目前內容）
2. 官方資料（台電、能源署等）取得與交叉驗證（後續）
3. Leaflet 互動網頁（後續）

需求來源見 `taiwan-power-map-plan.md`；規格與決策紀錄見 `docs/spectra/`。

## 安裝

需要 [uv](https://docs.astral.sh/uv/)（不需要 sudo，也不需要 Homebrew）。uv 會自動安裝 Python 3.12 與相依套件：

```bash
uv sync
```

## 使用

| 指令 | 作用 |
| --- | --- |
| `make data` | 從零產出全部資料：下載快照（已存在則跳過）→ 抽取 → 設施 → 電力線 → 統計 |
| `make extract` | 只下載與抽取，印出抽取摘要（數量、多能源筆數、離島排除數） |
| `make test` | 執行全部單元測試 |
| `make clean` | 刪除中間檔與輸出檔，保留已下載的快照 |

可調參數（在 `make` 後面加上即可，例如 `make data DEDUP_DISTANCE_M=300`）：

| 參數 | 預設 | 說明 |
| --- | --- | --- |
| `MAIN_BBOX` | `119.3,21.8,122.2,25.4` | 本島範圍框（西、南、東、北） |
| `ROOFTOP_THRESHOLD_MW` | `1` | 獨立太陽能發電機小於此容量即排除 |
| `DEDUP_DISTANCE_M` | `500` | 同名點與面相距小於此距離即合併 |

## 輸出

| 檔案 | 內容 |
| --- | --- |
| `data/processed/plants.geojson` | 設施點（電廠與獨立發電機） |
| `data/processed/lines.geojson` | 電力線（line、minor_line、cable），每個 OSM way 一筆 |
| `data/processed/stats.json` | 快照時間、數量、缺值、分類與排除統計 |
| `data/processed/dedup_log.csv` | 每一筆歸併、排除、合併的紀錄，方便人工複查 |

## 資料原則

- **缺值保持 `null`**：不補零、不輸出空字串、不補線。缺電壓的線 `voltage_class` 為 `missing`。
- **不替多能源設施決定主要能源**：來源標籤含多種能源（例如 `coal;gas`）時，`energy` 為 `mixed`，`energy_sources` 保留全部來源（例如 `["coal","gas"]`）。篩選時以 `energy_sources` 為準。
- **資料來源可追溯**：`capacity_source`、`energy_data_source`、`voltage_source` 標示屬性值的來源；目前只有 OSM，值為 `osm`，沒有值時為 `null`。
- **範圍**：台灣本島與鄰近島嶼（含綠島、蘭嶼、小琉球、龜山島、彰化外海風場）。金門、馬祖、澎湖與福建沿海圖徵暫不納入，排除數量記在 `stats.json`。跨界的線（例如台澎海纜）整條保留，不裁切。
- **資料只來自 OSM**：OSM 是志願者編輯的資料，可能不完整或不一致。設施存在不等於運轉中。與官方資料的交叉驗證是後續工作。
- 圓點大小不代表容量，線寬不代表潮流。

## 技術選擇

原計畫用 `osmium-tool` CLI 過濾與匯出 OSM 資料。因為開發機沒有 Homebrew，改用 [pyosmium](https://osmcode.org/pyosmium/)（PyPI 套件 `osmium`）在 Python 內完成相同工作，整個環境只靠 uv 就能建立。距離與簡化在 EPSG:3826（TWD97 / TM2）計算。

## 資料來源與授權

- 地圖資料 © OpenStreetMap contributors，以 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/) 授權。快照來源：Geofabrik（`https://download.geofabrik.de/asia/taiwan-latest.osm.pbf`）。
- 輸出的 GeoJSON 為 OSM 的衍生資料庫，同樣適用 ODbL 1.0。
