# PowerMap — 台灣電力地圖

從 OpenStreetMap（OSM）台灣快照取出發電設施與電力線，整理成可重跑、可檢查的 GeoJSON，再做成可篩選的互動地圖。

- 網站：https://sweetcowcow.github.io/PowerMap/

專案包含三個部分：

1. **OSM 資料管線**
2. **台電官方開放資料取得與交叉驗證**
3. **Leaflet 互動網頁**（`web/`）

需求來源見 `taiwan-power-map-plan.md`；規格與決策紀錄見 `docs/spectra/`。

## 安裝

需要 [uv](https://docs.astral.sh/uv/)（不需要 sudo，也不需要 Homebrew）。uv 會自動安裝 Python 3.12 與相依套件：

```bash
uv sync
```

## 使用

| 指令 | 作用 |
| --- | --- |
| `make data` | 從零產出全部資料：下載 OSM 快照（已存在則跳過）→ 抽取 → 設施 → 官方清單 → 補值 → 電力線 → 統計。官方資料讀 repo 內的快照，不連網 |
| `make extract` | 只下載與抽取，印出抽取摘要（數量、多能源筆數、離島排除數） |
| `make official-download` | 連網下載一份新的台電官方資料快照到 `data/official/raw/<日期>/`（下載後請 commit） |
| `make crosswalk-candidates` | 產生 `data/official/crosswalk_candidates.csv`，供人工建立對照表 |
| `make boundaries` | 連網下載內政部國土測繪中心的縣市界線（data.gov.tw 7442），簡化後輸出 `data/processed/counties.geojson`（下載後請 commit）。不屬於 `make data` |
| `make web` | 把 `data/processed/` 的六個檔案複製到 `web/data/`，不會觸發資料管線 |
| `make all` | `make data` 加上 `make web` |
| `make test` | 執行資料管線的單元測試（pytest） |
| `make test-web` | 執行網頁的單元測試（`node --test`，不需要 npm 套件） |
| `make clean` | 刪除中間檔與輸出檔，保留已下載的快照 |

可調參數（在 `make` 後面加上即可，例如 `make data DEDUP_DISTANCE_M=300`）：

| 參數 | 預設 | 說明 |
| --- | --- | --- |
| `MAIN_BBOX` | `119.3,21.8,122.2,25.4` | 本島範圍框（西、南、東、北） |
| `ROOFTOP_THRESHOLD_MW` | `1` | 獨立太陽能發電機小於此容量即排除 |
| `DEDUP_DISTANCE_M` | `500` | 同名點與面相距小於此距離即合併 |
| `CAPACITY_DIFF_THRESHOLD` | `0.2` | OSM 與官方容量相差超過此比例即列入 `official_diff.csv` |
| `OFFICIAL_DIR` | 最新日期的快照 | 指定使用哪一份官方資料快照 |

參數改變時，`make data` 會自動重跑受影響的步驟。

## 輸出

| 檔案 | 內容 |
| --- | --- |
| `data/processed/plants.geojson` | 設施點（電廠與獨立發電機），含官方對照欄位 `official_id`、`energy_primary` |
| `data/processed/lines.geojson` | 電力線（line、minor_line、cable），每個 OSM way 一筆 |
| `data/processed/substations.geojson` | 變電所（`power=substation`），每個 OSM 物件一個點（面取內部代表點），含名稱、營運者、種類（`substation` 標籤）、最高電壓與電壓分級（和電力線相同的 5 級）。不去重 |
| `data/processed/stats.json` | 快照時間、數量、缺值、分類與排除統計；變電所另有 `substations`、`substations_missing_voltage`、`substations_by_voltage_class` |
| `data/processed/dedup_log.csv` | 每一筆歸併、排除、合併的紀錄（含依官方對照表合併的 `official_same_plant`），方便人工複查 |
| `data/processed/official_diff.csv` | OSM 與官方容量差異超過門檻的電廠 |
| `data/processed/unmatched.csv` | 沒有對應到 OSM 的官方電廠：`no_osm`（已審閱，OSM 沒有）、`unreviewed`（尚未審閱）、`osm_missing`（對照表的 OSM id 已失效） |

## 網頁

```bash
make web
python -m http.server -d web 8000   # 開啟 http://localhost:8000/
```

- 純 HTML/JS，以 CDN 載入 Leaflet 1.9.4 與 Leaflet.markercluster 1.5.3，不需要打包工具。篩選、Popup 等邏輯在 `web/lib.js`，畫面接線在 `web/app.js`。
- 預設底圖是縣市界輪廓，不請求外部圖磚；右上角可以切換成 OSM 標準圖磚（調暗或原色，只當選用圖層，符合 OSM 圖磚的低流量使用政策）或國土測繪中心正射影像。
- 地圖上方的定位列可以切換縣市、搜尋電廠名稱（本地資料，邊打字邊列出），或按 Enter 搜尋地名與地址（送到 OSM Nominatim）。
- 側欄以電力線為主：電壓篩選預設全勾；發電設施的能源篩選預設全部不勾，需要時再勾選。
- 變電所畫成方形，顏色跟著電壓等級（缺電壓為灰色空心方形），跟著電壓勾選與「只看資料缺口」一起開關，另有「變電所」開關；搜尋框也能找變電所名稱。
- 能源篩選以 `energy_sources` 為準：多種能源的設施，只要勾選其中一種就會顯示。
- 獨立發電機依能源分組聚合，聚合點大小固定、數字是支數，放大到 zoom 12 以上就逐支顯示；電廠不聚合。
- 「只看資料缺口」只顯示缺容量的設施與缺電壓的線，並和能源、電壓篩選同時生效。
- push 到 `main` 後，GitHub Actions（`.github/workflows/pages.yml`）會先跑 `make test-web`，再執行 `make web`，最後發佈 `web/` 到 GitHub Pages。CI 不跑 Python 資料管線，所以資料更新後要先在本機執行 `make data` 並 commit `data/processed/`。

## 官方資料與對照表

官方資料來自政府資料開放平臺的四份台電資料集，沒有座標，所以和 OSM 的對應靠人工確認的對照表：

| 資料集 | 用途 |
| --- | --- |
| [8934 水火力發電廠位置及機組設備](https://data.gov.tw/dataset/8934) | 電廠、機組容量、燃料 |
| [10858 核能發電廠位置及機組設備](https://data.gov.tw/dataset/10858) | 核能機組容量 |
| [17141 再生能源各場址資料](https://data.gov.tw/dataset/17141) | 台電風力、太陽光電、地熱場址 |
| [8931 各機組發電量即時資訊](https://data.gov.tw/dataset/8931) | 只取民營電廠機組與容量 |

維護流程：

1. `make official-download` 取得新快照並 commit（同一天不可重複下載）。
2. `make crosswalk-candidates`，依候選檔審閱，編輯 `data/official/crosswalk.csv`：
   - 欄位：`official_id,osm_ids,relation,note`，`osm_ids` 以 `;` 分隔。
   - `same`：這些 OSM 設施都是這座電廠，合併到第一個 id；OSM 缺容量時以官方值補上。
   - `part`：每個 OSM 設施是這座官方電廠的一部分（例如分廠），不合併、不補容量。
   - `none`：已審閱，OSM 沒有對應。
3. `make data`，確認終端輸出的「Unreviewed official plants」與「ignored crosswalk ids」都是 0。

補值規則：只在 OSM 缺容量時補官方值（`capacity_source: "taipower"`），OSM 原值不覆蓋；`energy_primary` 取官方容量最大的燃料（`energy_primary_source: "taipower"`），`energy`／`energy_sources` 仍是 OSM 判定。

## 資料原則

- **缺值保持 `null`**：不補零、不輸出空字串、不補線。缺電壓的線 `voltage_class` 為 `missing`。
- **不替多能源設施決定主要能源**：來源標籤含多種能源（例如 `coal;gas`）時，`energy` 為 `mixed`，`energy_sources` 保留全部來源（例如 `["coal","gas"]`）。篩選時以 `energy_sources` 為準。
- **資料來源可追溯**：`capacity_source`、`energy_data_source`、`energy_primary_source`、`voltage_source` 標示屬性值的來源：`osm` 或 `taipower`，沒有值時為 `null`。
- **範圍**：台灣本島與鄰近島嶼（含綠島、蘭嶼、小琉球、龜山島、彰化外海風場）。金門、馬祖、澎湖與福建沿海圖徵暫不納入，排除數量記在 `stats.json`。跨界的線（例如台澎海纜）整條保留，不裁切。
- **OSM 為主、官方為輔**：OSM 是志願者編輯的資料，可能不完整或不一致。官方資料只涵蓋台電電廠、台電再生能源場址與民營火力電廠，民營太陽能與風力沒有逐場官方資料。線路電壓沒有官方資料可補。設施存在不等於運轉中（例如核一、核二、核三已停止運轉，龍門未曾商轉）。
- 圓點大小不代表容量，線寬不代表潮流。

## 技術選擇

原計畫用 `osmium-tool` CLI 過濾與匯出 OSM 資料。因為開發機沒有 Homebrew，改用 [pyosmium](https://osmcode.org/pyosmium/)（PyPI 套件 `osmium`）在 Python 內完成相同工作，整個環境只靠 uv 就能建立。距離與簡化在 EPSG:3826（TWD97 / TM2）計算。

## 資料來源與授權

- 地圖資料 © OpenStreetMap contributors，以 [ODbL 1.0](https://opendatacommons.org/licenses/odbl/) 授權。快照來源：Geofabrik（`https://download.geofabrik.de/asia/taiwan-latest.osm.pbf`）。
- 輸出的 GeoJSON 為 OSM 的衍生資料庫，同樣適用 ODbL 1.0。
- 縣市界線：內政部國土測繪中心「直轄市、縣市界線(TWD97經緯度)」（data.gov.tw 7442），政府資料開放授權條款第 1 版；網址、下載時間與 SHA-256 記在 `counties.geojson` 的 `source` 欄位。
- 選用圖磚：OpenStreetMap 標準圖磚，© OpenStreetMap contributors。
- 選用正射影像：內政部國土測繪中心 WMTS（PHOTO2），政府資料開放授權條款第 1 版。
- 地名搜尋：OpenStreetMap Nominatim（按下搜尋才送出查詢），© OpenStreetMap contributors。
- 官方資料：台灣電力股份有限公司，經政府資料開放平臺（data.gov.tw）以[政府資料開放授權條款第 1 版](https://data.gov.tw/license)提供。原始檔與下載時間、SHA-256 記錄在 `data/official/raw/<日期>/manifest.json`。
