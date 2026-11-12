## 1. 官方資料取得與正規化

- [x] 1.1 依「官方原始檔依下載日期保存並進 git」實作 Official snapshot download：`powermap/official.py` 的 `download` 子命令與 `make official-download`。四個檔先下載到暫存目錄，全部成功後才移到 `data/official/raw/<YYYY-MM-DD>/`，並寫入 `manifest.json`（含 SHA-256 與授權）；目錄已存在時非零退出。驗證：`tests/test_official.py` 以 `file://` 網址測試成功、單檔失敗不留目錄、同日目錄拒絕覆寫三種情境。
- [x] 1.2 [after: 1.1] 執行 `make official-download` 取得真實快照，確認四個檔的筆數（預期約為 176、9、104 行與 213 列，量測值以實際輸出為準），並 commit `data/official/raw/<date>/`。驗證：`git ls-files data/official/raw` 列出四個檔與 `manifest.json`。
- [x] 1.3 [after: 1.1] 依「官方資料正規化成電廠層級清單」與「主要能源取官方容量最大的燃料」實作 Official plant normalization、Official fuel mapping and primary energy、Official scope filter：`powermap/official.py` 的 `normalize` 子命令。讀取快照目錄（預設最新日期，可用 `OFFICIAL_DIR` 指定），輸出 `data/interim/official_plants.json`；缺欄位時非零退出並印出欄位名稱。驗證：`tests/test_official.py` 涵蓋大潭 7 部機組加總為 4984.2 MW、海湖只取民營列且排除小計、燃料對應範例表全部 8 列、興達主要能源為 `gas`、金門馬祖澎湖 3 座排除、缺欄位錯誤。

## 2. 對照表

- [x] 2.1 依「對應靠人工確認的對照表，程式只產生候選」實作 Name normalization 與 Crosswalk candidates：`powermap/crosswalk.py` 的 `normalize_name` 與 `candidates` 子命令，以及 `make crosswalk-candidates`。輸出 `data/official/crosswalk_candidates.csv`，並印出 `exact`、`contains`、`none` 各有幾座官方電廠。驗證：`tests/test_crosswalk.py` 涵蓋名稱正規化範例表全部 7 列、興達 `contains` 候選、核三 `none` 列。
- [x] 2.2 [after: 2.1] 依「對照表以 relation 區分「同一座」與「其中一部分」」實作 Crosswalk file validation：`powermap/crosswalk.py` 的 `load_crosswalk`。重複的 `official_id`、重複的 OSM id、不合法的 `relation` 都非零退出；不存在的 `official_id` 或 OSM id 印警告並忽略。驗證：`tests/test_crosswalk.py` 涵蓋 OSM id 重複、`relation` 不合法、失效 OSM id 只套用剩下的 id、整列失效回報 `osm_missing`。

## 3. 補值與輸出

- [x] 3.1 依「補值步驟獨立成 enrich，設施步驟改輸出到中間檔」修改 Facility dataset output：設施步驟改寫 `data/interim/facilities_osm.geojson` 與 `data/interim/dedup_log_osm.csv`，`PROPERTY_KEYS` 在 `missing_energy` 之後新增 `official_id`、`energy_primary`、`energy_primary_source`，中間檔中三者皆為 `null`。驗證：更新後的 `tests/test_facilities.py` 斷言新的欄位順序與三個 `null` 值，`uv run pytest` 全部通過。
- [x] 3.2 [after: 2.2, 3.1] 實作 Official enrichment 與 Facility value provenance 的 `taipower` 來源：`powermap/enrich.py`。
  - `same`：合併到第一個存在的 id，累加 `n_generators`，記錄 `official_same_plant` 與距離；OSM 缺容量時以官方值補上。
  - `part`：不合併，也不補容量。
  - `same` 與 `part` 都設定 `official_id`、`energy_primary`、`energy_primary_source`。
  - OSM 容量不覆蓋；`energy`、`energy_sources` 不變。
  - 輸出 `data/processed/plants.geojson` 與 `data/processed/dedup_log.csv`（OSM 去重紀錄在前，官方合併紀錄在後）。

  驗證：`tests/test_enrich.py` 涵蓋大潭合併補值、興達不覆蓋 OSM 容量、大甲溪 `part`、未在對照表的設施三個欄位為 `null`、去重紀錄順序。
- [x] 3.3 [after: 3.2] 依「容量差異門檻預設 20%」實作 Discrepancy and unmatched reports：輸出 `official_diff.csv`（門檻參數 `--capacity-diff-threshold`，`diff_ratio` 取 3 位小數）、`unmatched.csv`（`no_osm`、`unreviewed`、`osm_missing`）與 `data/interim/enrich_meta.json`；終端印出未審閱數與失效 id 數。驗證：`tests/test_enrich.py` 涵蓋 4326 對 3325.95 的 `diff_ratio` 為 0.301、120 對 100 在門檻 0.2 時不列出、`ipp:海湖` 未審閱列入 `unreviewed`。
- [x] 3.4 [after: 3.3] 修改 Statistics file：`stats.json` 新增 `official` 物件，所有數字都從輸出檔計算。驗證：`tests/test_stats.py` 新增 `unmatched.csv` 有 2 列 `unreviewed`、`official_diff.csv` 有 1 列時的計數情境，既有的統計測試仍通過。

## 4. 管線串接與文件

- [x] 4.1 [after: 1.3, 3.4] Makefile 串接：`make data` 依序執行 抽取 → 設施 → 官方正規化 → 補值 → 電力線 → 統計，全程不連網。新增 `OFFICIAL_DIR`、`CAPACITY_DIFF_THRESHOLD` 參數，沿用參數戳記機制；`make crosswalk-candidates` 依賴設施與官方正規化的輸出。README 補上官方資料來源、授權標示（政府資料開放授權條款第 1 版）與對照表維護流程。驗證：在沒有 `crosswalk.csv` 時執行 `make data` 成功，且所有官方電廠都以 `unreviewed` 列入 `unmatched.csv`；改 `CAPACITY_DIFF_THRESHOLD` 後只有補值與統計重跑。

## 5. 人工對照與驗收

- [x] 5.1 [after: 1.2, 4.1] 以真實資料執行 `make crosswalk-candidates`，把候選整理成表格交給使用者審閱：每座官方電廠的候選、建議的 relation 與理由。依使用者確認的結果寫入 `data/official/crosswalk.csv`。驗證：使用者確認對照表內容；`make data` 回報未審閱數為 0，失效 id 數為 0。
- [x] 5.2 [after: 5.1] 資料面驗收，結果整理成表格回報使用者：
  - 大潭只剩一筆設施
  - 興達列在 `official_diff.csv`
  - 補上容量的設施數與缺容量比例的變化
  - `official_diff.csv`、`unmatched.csv` 全部列出
  - 所有缺值仍為 `null`

  驗證：報告已交付，且使用者對差異門檻是否調整做出決定。
- [x] 5.3 [after: 5.2] 依使用者決定調整 `CAPACITY_DIFF_THRESHOLD`（若有變更），重跑 `make data`，以 git commit 保存 `data/official/` 與 `data/processed/` 的輸出。驗證：`git status` 乾淨，`stats.json` 的 `official.unmatched.unreviewed` 為 0。

## 變更紀錄

2026-11-12 實作 1.3 時發現：17141 的發電站名稱本身含「/」（例如 `中科E/S太陽光電發電站/Zhongke E/S Solar Power Station`），以第一個「/」切割會截斷成「中科E」。官方正規化與名稱正規化改為從「其後全為 ASCII 的第一個 /」切掉英文名稱，spec 與 design 同步更新，名稱正規化範例新增一列；範例「協和電廠－珠山」更正為 NFKC 後的「協和電廠-珠山」。另實測排除的離島官方電廠為 13 座（水火力 3 座＋再生能源 10 座），非 design 估計的 3 座。
