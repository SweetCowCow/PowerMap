# 台灣電力地圖複製計畫（OSM → Python → Leaflet）

> 給 Claude Code 的實作規格。目標：從 OpenStreetMap 快照取出台灣的發電設施與電力線圖徵，整理成 GeoJSON，並做成一個可篩選、可點選的 Leaflet 互動網頁。
> 參考作品：GEOMNI〈電從哪裡來？台灣電力的空間骨架〉（#30DayMapChallenge 2026 Day 12）。

---

## 1. 範圍

**要做**

1. 用 osmium 從 Geofabrik 台灣快照濾出電力相關圖徵
2. 用 Python（GeoPandas / Shapely）清理、分類、去重、統計缺值
3. 輸出兩個 GeoJSON（設施點、電力線）＋一個統計 JSON
4. 用 Leaflet 做單頁互動地圖：縮放、能源篩選、電壓篩選、點選看屬性、只看資料缺口

**先不做（列為後續）**

- Matplotlib 靜態海報版
- 台電公開機組表的比對補值（第 6 節列為選配階段）
- 即時發電資料

**原則（沿用原作）**

- 缺值保持 `null`，不補零、不隱藏；缺電壓的線用虛線畫出來
- 圓點大小不代表容量、線寬不代表潮流
- 不自行補畫連線

---

## 2. 環境與工具

| 用途 | 工具 |
|---|---|
| OSM 過濾 | `osmium-tool`（CLI） |
| 資料處理 | Python 3.11+、`geopandas`、`shapely`、`pandas`、`pyogrio` |
| 前端 | Leaflet 1.9（CDN）、純 HTML/JS，不需打包工具 |
| 本機預覽 | `python -m http.server` |

安裝：

```bash
# macOS
brew install osmium-tool
# Ubuntu
sudo apt install osmium-tool

pip install geopandas shapely pandas pyogrio
```

---

## 3. 專案結構

```
taiwan-power-map/
├── README.md
├── Makefile                  # make data / make web / make all
├── data/
│   ├── raw/                  # taiwan-latest.osm.pbf、縣市界（不進 git）
│   ├── interim/              # power.osm.pbf、power.geojsonseq
│   └── processed/            # plants.geojson、lines.geojson、stats.json
├── scripts/
│   ├── 01_download.sh
│   ├── 02_extract.sh
│   ├── 03_build_facilities.py
│   ├── 04_build_lines.py
│   └── 05_stats.py
├── web/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── data/                 # 由 processed 複製過來
└── tests/
    └── test_parsers.py
```

---

## 4. 資料來源

| 資料 | 來源 | 授權 | 備註 |
|---|---|---|---|
| OSM 台灣快照 | Geofabrik `https://download.geofabrik.de/asia/taiwan-latest.osm.pbf` | ODbL 1.0 | 需標示 © OpenStreetMap contributors |
| 縣市界 | 國土測繪中心「直轄市、縣市界線」（政府資料開放平臺 data.gov.tw 搜尋下載） | 政府資料開放授權條款第 1 版 | 只當底圖輪廓，可簡化 |
| 台電機組／場址表（選配） | 台電公開資料、data.gov.tw | 政府資料開放授權條款第 1 版 | 第二階段比對用 |

**待確認**：Geofabrik 台灣範圍是否含金門、馬祖、澎湖；下載後用縣市界疊圖檢查，缺的話改抓含該區的範圍再裁切。

記錄快照時間（寫進 `stats.json` 與網頁頁尾）：

```bash
osmium fileinfo -e data/raw/taiwan-latest.osm.pbf | grep -i timestamp
```

---

## 5. 資料處理流程

### 5.1 下載（01_download.sh）

```bash
mkdir -p data/raw data/interim data/processed
curl -L -o data/raw/taiwan-latest.osm.pbf \
  https://download.geofabrik.de/asia/taiwan-latest.osm.pbf
```

### 5.2 osmium 過濾與匯出（02_extract.sh）

```bash
# 只留電力相關的 node / way / relation
osmium tags-filter data/raw/taiwan-latest.osm.pbf \
  nwr/power=plant,generator,line,minor_line,cable \
  -o data/interim/power.osm.pbf --overwrite

# 匯出成逐行 GeoJSON，保留 OSM 類型與 id
osmium export data/interim/power.osm.pbf \
  --add-unique-id=type_id \
  -f geojsonseq -o data/interim/power.geojsonseq --overwrite
```

注意事項：

- `osmium export` 會把 `type=multipolygon` 的 relation 組成面；`type=site` 之類的 relation 不會有幾何，需要的話另外用 pyosmium 處理（先記錄數量，不急著處理）
- 封閉 way 可能同時被輸出成線與面，依 `power` 值決定取哪種幾何（plant/generator 取面，line/cable 取線）
- `power=substation`、`power=tower` 這版先不取；之後想加變電所再擴充

### 5.3 OSM 標籤對照

| 圖徵 | 主標籤 | 需要的屬性標籤 |
|---|---|---|
| 電廠 | `power=plant` | `name`、`name:zh`、`name:en`、`operator`、`plant:source`、`plant:method`、`plant:output:electricity` |
| 發電機 | `power=generator` | `name`、`generator:source`、`generator:method`、`generator:output:electricity`、`generator:type` |
| 輸電線 | `power=line` | `voltage`、`cables`、`circuits`、`operator`、`name` |
| 次級線 | `power=minor_line` | `voltage` |
| 電纜（地下／海底） | `power=cable` | `voltage`、`location` |

### 5.4 設施整理（03_build_facilities.py）

1. 讀 `power.geojsonseq`，取 `power in (plant, generator)`
2. **幾何轉點**：面與線取 `representative_point()`（保證落在面內），保留原始幾何類型到 `geom_src`
3. **能源分類** `energy`：來源欄位為 `plant:source` 或 `generator:source`，先轉小寫、以 `;` 切開

   | 類別 | 規則 |
   |---|---|
   | `solar` | 僅含 solar |
   | `wind` | 僅含 wind |
   | `hydro` | 僅含 hydro |
   | `gas` | 僅含 gas |
   | `coal` | 僅含 coal |
   | `nuclear` | 僅含 nuclear |
   | `geothermal` | 僅含 geothermal |
   | `other` | oil、diesel、biomass、biogas、waste，或多種來源並列 |
   | `unknown` | 沒有 source 標籤 |

4. **容量解析** `capacity_mw`：解析 `plant:output:electricity` / `generator:output:electricity`
   - 支援 `550 MW`、`1.2 GW`、`499 kW`、`4500 kWp`、純數字、`yes`
   - 無法解析或為 `yes` → `null`，另存原字串到 `capacity_raw`
5. **去重與合併**（原作說「合併已辨識的重複設施」，建議規則如下，先用保守版本）
   - 落在某個 `plant` 面內的 `generator` → 不單獨出圖，計數寫回該 plant 的 `n_generators`
   - 不屬於任何 plant 的 `generator`：
     - `generator:location=roof` 或容量 < 門檻（預設 1 MW，可調參數）的屋頂型太陽能 → 預設排除，數量寫進統計
     - 其餘保留為獨立設施
   - 同名且距離 < 500 m（用 EPSG:3826 計算）的 node 與 way → 保留面那筆
   - 每個合併動作寫進 `data/processed/dedup_log.csv`，方便人工複查
6. 輸出欄位見第 5.6 節

### 5.5 電力線整理（04_build_lines.py）

1. 取 `power in (line, minor_line, cable)` 且幾何為線
2. **電壓解析** `voltage_max_kv`
   - `voltage` 單位是伏特，可能是 `345000`、`345000;161000`、`161000;69000;11400`
   - 以 `;` 切開，取數值最大者除以 1000；非數字 → `null`
   - 原字串保留到 `voltage_raw`
3. **電壓分級** `voltage_class`

   | 值 | 條件 | 圖面樣式 |
   |---|---|---|
   | `ehv` | ≥ 345 kV | 橘黃實線 |
   | `hv` | 161 – <345 kV | 淺藍實線 |
   | `mv` | 69 – <161 kV | 灰藍實線 |
   | `lv` | < 69 kV | 深灰實線 |
   | `missing` | 無電壓 | 粉紫虛線 |

4. 不合併、不補線；每個 OSM way 一段
5. 幾何簡化：`simplify(tolerance≈10 m, preserve_topology=True)`（在 EPSG:3826 下做，再轉回 EPSG:4326），座標四捨五入到小數 5 位以縮小檔案

### 5.6 輸出結構

`plants.geojson`（Point，EPSG:4326）

```json
{
  "osm_id": "w123456",
  "osm_url": "https://www.openstreetmap.org/way/123456",
  "kind": "plant",
  "name": "興達發電廠",
  "operator": "台灣電力公司",
  "energy": "coal",
  "source_raw": "coal;gas",
  "capacity_mw": null,
  "capacity_raw": null,
  "n_generators": 9,
  "missing_capacity": true,
  "missing_energy": false
}
```

`lines.geojson`（LineString）

```json
{
  "osm_id": "w234567",
  "osm_url": "https://www.openstreetmap.org/way/234567",
  "kind": "line",
  "voltage_max_kv": 345,
  "voltage_raw": "345000;161000",
  "voltage_class": "ehv",
  "missing_voltage": false,
  "location": null
}
```

`stats.json`（05_stats.py）

```json
{
  "snapshot": "2026-11-02T21:21:00Z",
  "built_at": "…",
  "facilities": 0,
  "lines": 0,
  "lines_missing_voltage": 0,
  "facilities_missing_capacity": 0,
  "by_energy": {},
  "by_voltage_class": {},
  "excluded_rooftop_solar": 0
}
```

---

## 6. 選配階段：台電公開表比對

- 以名稱正規化（去掉「發電廠／電廠／分廠」、全半形、臺→台）＋距離做比對
- 只在 OSM 缺值時補上，並用 `capacity_source: "taipower"` 標明來源；OSM 原值不覆蓋
- 沒比對到的列進 `unmatched.csv`

---

## 7. 互動網頁（web/）

**底圖**：深色背景＋縣市界輪廓（自己的 GeoJSON），不依賴外部圖磚也能看；可加一個深色圖磚層當選項。

**效能**：`L.map(..., { preferCanvas: true })`，線用 canvas renderer；設施用 `L.circleMarker`。

**功能清單**

| 功能 | 做法 |
|---|---|
| 縮放／平移 | Leaflet 預設；初始視角 `fitBounds` 台灣本島，另放金門、馬祖快速跳轉鈕 |
| 能源篩選 | 側欄勾選框（9 類），含「全選／全不選」 |
| 電壓篩選 | 側欄勾選框（5 級，含缺電壓） |
| 只看資料缺口 | 一個切換鈕：只顯示 `missing_voltage` 的線與 `missing_capacity` 的設施 |
| 點選設施 | Popup：名稱、能源、容量（缺值顯示「未填」）、營運者、OSM 連結 |
| 點選線段 | Popup：最高電壓、原始 voltage 字串、OSM 連結 |
| 圖例 | 與篩選器合一，顏色對照原作 |
| 統計面板 | 讀 `stats.json`，顯示設施數、線段數、缺電壓數、缺容量數；隨篩選即時更新目前顯示數量 |
| 頁尾 | 資料來源、快照時間、授權、「不是即時供電圖」聲明 |
| 手機版 | 側欄收合成底部抽屜 |

**配色（接近原作）**

```
背景        #0b1826     陸地 #142534   縣市界 #22384a
太陽能 #ffd15c   風力 #6fe0c0   水力 #5aa9ff   燃氣 #ff9a6b
燃煤   #e0605f   其他 #b98ad9   地熱 #d98a3d   未填 #8a94a0
核能   白色空心菱形
≥345kV #f0b85a   161kV #6cc4e8   69kV #4a7f9c   <69kV #3d5566
缺電壓 #b58aa8 虛線
```

---

## 8. 驗收與檢查

- [ ] `make all` 可從零跑完，產出三個檔案
- [ ] 設施數與線段數量級接近原作（約 700 設施、約 2,100 段線）；差距大時檢查去重與屋頂太陽能門檻
- [ ] 抽查 10 個已知電廠（大潭、通霄、興達、台中、萬大、核一二三、和平、麥寮等）位置與分類正確
- [ ] `voltage`、容量解析器有單元測試（含多值、單位、非數字）
- [ ] 缺值在 GeoJSON 為 `null`，不是 0 或空字串
- [ ] 金門、馬祖、澎湖有資料
- [ ] 網頁在手機與桌機都能操作；`lines.geojson` 壓縮前 < 5 MB
- [ ] 頁尾有 ODbL 與政府資料開放授權標示

**已知風險**

- OSM 標註不完整且不一致，數字不會與原作完全相同（快照日期、去重規則都不同）
- 離岸風場可能是整場一個 plant，也可能是一支支 generator，需看實際資料決定是否聚合
- 設施存在不等於運轉中；核能僅標示位置

---

## 9. 實作順序（給 Claude Code）

1. 建專案骨架、Makefile、安裝依賴
2. 完成 01、02 腳本，先印出各 `power=*` 的數量與幾何類型分布，回報後再往下
3. 寫解析器（能源、容量、電壓）與單元測試
4. 完成 03、04、05，輸出 GeoJSON 與 `stats.json`，印出統計摘要
5. 做 Leaflet 頁面：先畫出來，再加篩選、Popup、缺口模式、統計面板
6. 跑第 8 節驗收清單，調整去重門檻
7. （選配）台電表比對、部署到 GitHub Pages 或 Cloudflare Pages

**開場指令範例**

> 請閱讀 `taiwan-power-map-plan.md`，依第 9 節順序實作。先做步驟 1–2，把各類圖徵數量與幾何類型分布印給我看，確認後再繼續。去重規則有疑問時先列出案例問我，不要自行決定。
