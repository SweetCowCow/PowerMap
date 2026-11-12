## Why

OSM 設施資料缺值多（實測 1,584 筆中 1,354 筆沒有容量），而且有同一座電廠被畫成多個範圍的重複（例如大潭、興達）。第一個 change 決定交由官方資料處理。台電在政府資料開放平臺公開了電廠、機組與再生能源場址清單，可以用來補容量、找出重複、標示主要能源，並在網頁上線前讓資料有官方依據。

## What Changes

- 新增官方資料取得：從 data.gov.tw 下載台電水火力電廠機組（8934）、核能機組（10858）、再生能源場址（17141）、各機組即時資訊（8931，只取民營電廠機組）。原始檔放在以下載日期命名的目錄，連同來源清單一起 commit 進 repo
- 新增官方資料正規化：把機組彙整成電廠層級的官方清單，含名稱、縣市、裝置容量（MW）、各燃料容量與主要能源；位於金門、馬祖、澎湖的電廠依既有範圍規則排除並計數
- 新增官方與 OSM 對照：程式依正規化名稱產出候選配對 `crosswalk_candidates.csv`，人工確認後存成 `data/official/crosswalk.csv` 進 git；管線只讀這張對照表，未審閱的官方項目列出供人工處理
- 新增補值與交叉驗證：OSM 缺容量時以官方值補上，標 `capacity_source: "taipower"`，不覆蓋 OSM 原值；兩邊都有值且差距超過門檻時列入 `official_diff.csv`；沒對到的官方項目列入 `unmatched.csv`
- 新增重複合併：對照表標為「同一座電廠」的多筆 OSM 設施合併為一筆，記入 `dedup_log.csv`
- 設施資料新增欄位 `official_id`、`energy_primary`、`energy_primary_source`；`energy` 與 `energy_sources` 不變
- **BREAKING**（僅影響中間檔）：設施步驟改輸出到 `data/interim/facilities_osm.geojson`，最終的 `data/processed/plants.geojson` 改由新的補值步驟產生
- 統計檔新增官方比對相關數字

## Non-Goals (optional)

（詳見 design.md 的 Goals / Non-Goals）

## Capabilities

### New Capabilities

- `official-power-data`: 官方開放資料的下載、版本保存與正規化成電廠層級清單
- `official-crosswalk`: 官方電廠與 OSM 設施的候選配對、人工對照表格式與檢查、補值、合併與差異報告

### Modified Capabilities

- `power-facility-dataset`: 設施輸出新增官方欄位、容量來源可為 `taipower`、最終輸出改由補值步驟產生
- `power-data-stats`: 統計檔新增官方比對、補值、未對應與差異數量

## Impact

- 新增程式：powermap/official.py、powermap/crosswalk.py、powermap/enrich.py（下載由 powermap/official.py 的 download 子命令負責）
- 修改程式：powermap/facilities.py（輸出路徑）、powermap/stats.py、Makefile、README.md
- 新增測試：tests/test_official.py、tests/test_crosswalk.py、tests/test_enrich.py；修改 tests/test_stats.py
- 新增資料：data/official/（原始檔、來源清單、對照表、候選配對）；data/processed/ 新增 unmatched.csv、official_diff.csv
- 新增依賴：無（沿用 Python 標準函式庫的 csv、json 與既有套件）
- 授權：官方資料為政府資料開放授權條款第 1 版，README 與輸出需標示出處
