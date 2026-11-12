## Context

第一個 change（build-power-data-pipeline，已封存）產出只依據 OSM 的 `plants.geojson`：1,584 筆設施中有 1,354 筆缺容量（實測），並有面對面重複（大潭兩個範圍、興達多一個未標能源的範圍）沒有處理。該 change 決定把重複判定與補值交給官方資料。

討論時實際查詢 data.gov.tw（2026-11-12）的結果：

| 資料集 | 內容 | 實測筆數 | 座標 |
| --- | --- | --- | --- |
| 8934 台電水火力電廠位置及機組設備（CSV） | 電廠、機組、地址、裝置容量（瓩）、燃料種類（水、煤、天然氣、重油、輕柴油） | 22 座電廠、175 部機組，含金門、馬祖、澎湖 3 座 | 無 |
| 10858 台電核能電廠位置及機組設備（CSV） | 電廠、機組、地址、裝置容量（MWe） | 8 部機組 | 無 |
| 17141 台電再生能源各場址資料（CSV） | 發電站、場址、能源別、裝置容量（瓩）、地址、申設狀態 | 68 座發電站、103 列 | 無 |
| 8931 台電各機組發電量即時資訊（JSON） | 機組類型、機組名稱、裝置容量（MW），含民營電廠 | 213 列，其中民營電廠機組 13 部（8 座電廠） | 無，也無地址 |

官方資料沒有座標，也找不到官方的輸電線路或電壓資料。授權皆為政府資料開放授權條款第 1 版。

## Goals / Non-Goals

**Goals:**

- 保存一份可追溯版本的官方原始檔，`make data` 不需連網即可重現
- 把官方資料正規化為電廠層級清單，含容量與主要能源
- 以人工確認過的對照表連結官方電廠與 OSM 設施
- OSM 缺容量時以官方值補上並標示來源；兩邊都有值時列出差異
- 合併對照表判定為同一座電廠的多筆 OSM 設施
- 列出沒有對應的官方電廠

**Non-Goals:**

- 不補線路電壓：查無官方資料
- 不處理民營太陽能、風力的逐場資料：能源署只提供 ODT 文件，不採用
- 不採用離岸風電潛力場址：那是規劃區，不是電廠
- 不標示運轉狀態（例如除役），留給網頁 change 決定
- 不做地理編碼（地址轉座標），也不用距離比對：官方資料沒有座標
- 不覆蓋 OSM 原有的容量值

## Decisions

### 官方原始檔依下載日期保存並進 git

`make official-download` 下載四個檔到 `data/official/raw/<YYYY-MM-DD>/`，並寫入 `manifest.json`，記錄每個檔的資料集編號、標題、網址、下載時間、SHA-256 與授權。同一天的目錄已存在時拒絕覆寫。`make data` 預設讀取最新日期的目錄，也可以用 `OFFICIAL_DIR` 指定。台電檔案沒有版本號，隨時會更新；檔案很小（估計合計不到 100 KB，由 1.2 下載後的實際大小確認），進 git 才能重現結果。替代方案是每次 `make data` 都即時下載，但那樣結果會隨下載時間改變，而且需要連網，所以不採用。

### 官方資料正規化成電廠層級清單

`powermap/official.py` 把四個來源轉成同一種電廠紀錄，寫到 `data/interim/official_plants.json`。

- `official_id` 依來源加前綴，在官方資料更新後仍保持穩定：
  - `tp-plant:<電廠名稱>`：8934、10858
  - `tp-re:<發電站中文名稱>`：17141，同一發電站的多個場址合併計算
  - `ipp:<機組名稱 # 之前的部分>`：8931 中機組類型以「民營電廠-」開頭且名稱不是「小計」的列
- 燃料對應：水→hydro、煤→coal、天然氣與燃氣→gas、核能→nuclear、太陽能→solar、陸域與離岸風力→wind、地熱→geothermal。重油、輕柴油與其他燃料→other。對應不到的燃料歸為 other，並記入警告。
- 縣市取地址前 3 個字，並把「臺」換成「台」；8931 沒有地址，縣市為 `null`。
- 縣市為金門縣、連江縣、澎湖縣的電廠排除並計數，與第一個 change 的範圍規則一致。

### 主要能源取官方容量最大的燃料

`energy_primary` 取該官方電廠各燃料裝置容量加總最大者；同分時依 `SOURCE_CATEGORIES` 的順序決定。只有對應到官方電廠的設施才有值，此時 `energy_primary_source` 為 `taipower`，其餘兩者皆為 `null`。`energy` 與 `energy_sources` 保持 OSM 判定，不受影響。

**Supersedes**: build-power-data-pipeline / 多能源設施標為 mixed 並保留全部來源（僅補充：主要能源改由官方資料提供，`mixed` 規則本身不變）

### 對應靠人工確認的對照表，程式只產生候選

`make crosswalk-candidates` 依正規化名稱產出 `data/official/crosswalk_candidates.csv`：NFKC 全半形轉換、「臺」換成「台」、去掉空白與結尾的英文名稱（從其後全為 ASCII 的第一個「/」起算，避免截斷「中科E/S」這類中文名）、去掉開頭的「台電」與「台灣電力公司」，並反覆去掉結尾的「發電廠」「發電站」「電廠」「分廠」「廠」。名稱完全相同的標為 `exact`；一方包含另一方，且較短的一方至少 2 個字的標為 `contains`。

人工審閱後寫成 `data/official/crosswalk.csv`，管線只讀這個檔。官方資料沒有座標，OSM 設施也沒有縣市欄位，所以候選不做縣市篩選。候選檔會列出官方縣市與 OSM 設施的座標和 OSM 連結，縣市由人工核對。

替代方案是全自動名稱比對，但它會把「大觀一廠／大觀二廠」「大甲溪發電廠」這類名稱配錯而不被發現，所以不採用。

### 對照表以 relation 區分「同一座」與「其中一部分」

`crosswalk.csv` 欄位為 `official_id,osm_ids,relation,note`：

- `same`：`osm_ids` 列出的設施都是這座電廠，合併到第一個 id，可補容量。
- `part`：每個設施只是這座官方電廠的一部分（例如大甲溪發電廠的各分廠），不合併，也不補容量，因為官方容量是總數；只標 `official_id` 與主要能源。
- `none`：已審閱但 OSM 沒有對應。

同一個 OSM id 不可出現在兩列。

### 補值步驟獨立成 enrich，設施步驟改輸出到中間檔

`powermap/facilities.py` 改為輸出：

- `data/interim/facilities_osm.geojson`
- `data/interim/dedup_log_osm.csv`

新的 `powermap/enrich.py` 讀取上述檔案、官方清單與對照表，輸出：

- `data/processed/plants.geojson`
- `data/processed/dedup_log.csv`：OSM 去重紀錄加上官方合併紀錄
- `data/processed/unmatched.csv`
- `data/processed/official_diff.csv`
- `data/interim/enrich_meta.json`

每個步驟只寫自己的檔，重跑結果一致。替代方案是讓 enrich 直接改寫 `plants.geojson`，但那樣重跑會疊加效果，所以不採用。

### 容量差異門檻預設 20%

OSM 與官方都有容量，且 |OSM − 官方| ÷ 官方 > 門檻時，列入 `official_diff.csv`。門檻用 `--capacity-diff-threshold` 指定，Makefile 預設 `CAPACITY_DIFF_THRESHOLD ?= 0.2`。20% 是自訂值，不是量測結果：已知興達 OSM 4,326 MW 對官方約 3,326 MW（實測），差約 30%，會被列出。實際列出的筆數在驗收時回報，由使用者決定是否調整。

## Implementation Contract

**Behavior**

- `make official-download`：連網下載官方檔，建立新的日期目錄，印出各檔筆數與 SHA-256。
- `make crosswalk-candidates`：產生候選檔，印出有 `exact`、`contains`、無候選的官方電廠數量。
- `make data`：不連網，依序執行 抽取 → 設施 → 官方正規化 → 補值 → 電力線 → 統計。結束時印出：
  - 未審閱的官方電廠數量
  - 對照表中失效的 id 數量
- 參數變更時自動重建，沿用第一個 change 的參數戳記機制。

**Interface / data shape**

`data/official/raw/<date>/` 內的檔案：

- `thermal_hydro.csv`（8934）
- `nuclear.csv`（10858）
- `renewable.csv`（17141）
- `units.json`（8931）
- `manifest.json`，格式為：

```json
{"downloaded_at": "2026-11-12T08:00:00Z", "license": "政府資料開放授權條款第1版",
 "files": [{"dataset_id": "8934", "title": "...", "url": "...", "file": "thermal_hydro.csv", "sha256": "..."}]}
```

`official_plants.json`：

```json
{"source_dir": "data/official/raw/2026-11-12", "excluded_outside_main_island": 3,
 "plants": [{"official_id": "tp-plant:興達發電廠", "dataset_id": "8934", "name": "興達發電廠",
             "name_normalized": "興達", "county": "高雄市", "address": "...",
             "capacity_mw": 3325.95, "capacity_by_source_mw": {"coal": 1100.0, "gas": 2225.95},
             "energy_primary": "gas", "n_units": 7}],
 "warnings": []}
```

其他檔案：

- `crosswalk_candidates.csv` 欄位：`official_id,official_name,county,official_capacity_mw,osm_id,osm_name,osm_kind,osm_capacity_mw,lon,lat,osm_url,match_type`。`match_type` 為 `exact`、`contains` 或 `none`；`none` 列的 OSM 欄位為空。
- `crosswalk.csv` 欄位：`official_id,osm_ids,relation,note`。`osm_ids` 以 `;` 分隔，`relation` 為 `same`、`part` 或 `none`。
- `unmatched.csv` 欄位：`official_id,name,county,capacity_mw,reason`。`reason` 為 `no_osm`、`unreviewed` 或 `osm_missing`。
- `official_diff.csv` 欄位：`official_id,osm_id,osm_capacity_mw,official_capacity_mw,diff_ratio`。
- `dedup_log.csv` 新增 action `official_same_plant`，`reason` 欄填 `official_id`，`distance_m` 為兩點距離（EPSG:3826）。
- 設施屬性在 `missing_energy` 之後依序新增 `official_id`、`energy_primary`、`energy_primary_source`；中間檔中三者皆為 `null`。

**Failure modes**

- 對照表中同一個 `official_id` 出現兩列，或同一個 OSM id 出現在兩列：非零退出，並印出衝突的列。
- `relation` 不是 `same`、`part`、`none` 三者之一：非零退出。
- 對照表的 `official_id` 不在官方清單中：印警告並忽略該列。
- 對照表的 OSM id 不在設施資料中：印警告並忽略該 id。整列都失效時，該官方電廠列入 `unmatched.csv`，`reason` 為 `osm_missing`。
- 官方檔欄位名稱與預期不符：非零退出，並印出缺少的欄位名稱。

**Acceptance criteria**

- `uv run pytest` 全部通過。新增測試涵蓋：
  - 四種來源的解析與燃料對應
  - 範圍排除
  - 名稱正規化範例
  - `same`、`part`、`none` 三種行為
  - 補值不覆蓋 OSM 值
  - 差異門檻
  - 對照表錯誤處理
- 以真實資料執行 `make data` 後，大潭只剩一筆設施，`興達發電廠` 出現在 `official_diff.csv`。

**Scope boundaries**

- In scope：官方資料下載與正規化、候選與對照表、補值、合併、差異與未對應報告、統計、README。
- Out of scope：網頁、線路、地理編碼、運轉狀態、能源署資料。

## Risks / Trade-offs

- [官方資料隨時更新，欄位可能改名] → 原始檔進 git 並記錄 SHA-256；欄位不符時明確失敗，不靜默產出錯誤資料。
- [人工對照表需要維護] → 官方電廠約 100 筆（估計：22 + 1 + 68 + 8 = 99 筆，扣除離島 3 筆，實際數字以正規化輸出為準）。新增或失效的項目會在 `make data` 輸出中列出，只需補看差異。
- [8931 是即時資料，民營電廠清單可能變動] → 只取容量與名稱，版本以下載當時的檔案為準。
- [`part` 關係不補容量，部分電廠仍會缺容量] → 這是刻意選擇：官方容量是總數，分配到各分廠沒有根據。
- [20% 門檻是自訂值] → 驗收時回報實際列出的筆數，由使用者決定。

## Migration Plan

- 設施步驟的輸出路徑改到 `data/interim/`，下游只有 stats 和新的 enrich 會讀取，在同一個 change 內一起修改。
- 已 commit 的 `data/processed/plants.geojson` 會在 7.x 驗收後以新版本取代。
- 回滾方式：revert 本 change 的 commit。

## Open Questions

- 無。對應方式、補值規則、主要能源、範圍已在 2026-11-12 討論中確定。
