## Context

專案目前只有 Spectra 設定與需求文件 `taiwan-power-map-plan.md`，沒有任何程式碼。本 change 實作該文件第 1–5、8、9 節中的資料管線部分，只使用 OSM 作為資料來源。後續兩個 change 依序為：官方資料取得與交叉驗證（擴充需求文件第 6 節），以及互動網頁（第 7 節），兩者都以本 change 的輸出檔為輸入。

本機環境（2026-11-12 實測）：

- 系統 Python 為 3.9.6，低於需求的 3.11
- 沒有 Homebrew，也沒有 osmium-tool CLI
- 有 `make`、`curl`、`jq`；機器為 Apple Silicon（arm64）

使用者已確認的取捨（2026-11-12）：

- 多種能源並列時標為 `mixed` 並保留全部來源（見下方決策），取代先前「取第一個來源」的做法，也覆寫需求文件分類表中「多來源 → other」的寫法
- 沒有單位的純數字容量視為 MW
- 先排除金門、馬祖、澎湖，專注台灣本島；綠島、蘭嶼、小琉球、龜山島保留
- 本 change 只用 OSM，但輸出要為官方資料補值預留資料來源欄位

## Goals / Non-Goals

**Goals:**

- `make data` 在乾淨的 clone 上可從零跑完，產出 `data/processed/plants.geojson`、`data/processed/lines.geojson`、`data/processed/stats.json`、`data/processed/dedup_log.csv`
- 解析器（能源、容量、電壓、電壓分級）為純函式並有單元測試
- 缺值一律輸出 JSON `null`，不補零、不輸出空字串、不補線
- 抽取後先輸出數量與幾何分布摘要，讓使用者確認後才進行後續整理
- 所有去重與歸併動作可追溯（寫入 `dedup_log.csv`）
- 每個屬性值都能看出來源（本 change 一律為 `osm`），讓下一個 change 補入官方資料時不需改動資料結構
- 輸出範圍為台灣本島與鄰近島嶼，排除數量可追溯

**Non-Goals:**

- Leaflet 互動網頁、縣市界底圖（第三個 change）
- 官方資料（台電、能源署等）的取得、比對、補值與總量驗證（第二個 change）
- 替多能源設施判定主要能源
- 金門、馬祖、澎湖（以及東沙、太平島等本島範圍框外的島嶼）的資料
- Matplotlib 靜態海報版
- 即時發電資料
- `power=substation`、`power=tower` 圖徵
- 無幾何的 relation（如 `type=site`）的幾何重建：只計數，不處理
- 部署（GitHub Pages / Cloudflare Pages）

## Decisions

### 以 uv 管理 Python 3.11 與相依套件

用 `uv`（安裝到 `~/.local/bin`，不需 sudo）建立專案虛擬環境並鎖定 Python 3.11 以上版本；相依套件宣告在 `pyproject.toml`，鎖檔 `uv.lock` 進 git。Makefile 的指令一律經 `uv run` 執行。

替代方案：安裝 Homebrew 再裝 python@3.11——需要管理員權限與互動安裝，且多一層系統相依，不採用。

### 以 pyosmium 取代 osmium-tool CLI 進行過濾與匯出

用 pyosmium（PyPI 套件 `osmium`，有 macOS arm64 wheel）讀取 `.osm.pbf`，以標籤過濾 `power` 值，組出面（含 `type=multipolygon` relation）與線幾何，寫成逐行 GeoJSON `data/interim/power.geojsonseq`。快照時間由 pbf header 的 `osmosis_replication_timestamp` 取得。

替代方案：需求文件原定的 `osmium tags-filter` + `osmium export`——需要 Homebrew 或自行編譯 osmium-tool，不採用。中間檔格式（geojsonseq）與欄位維持與原計畫相同，必要時可換回 CLI 而不影響下游。

### 程式邏輯放在 powermap 套件，Makefile 串接步驟

各步驟實作為 `powermap` 套件內的模組（`powermap.extract`、`powermap.facilities`、`powermap.lines`、`powermap.stats`），共用的解析邏輯集中在 `powermap.parsers`；下載用 `scripts/download.sh`。Makefile 以檔案相依串接：`make data` 依序執行下載（檔案存在則跳過）、抽取、設施、電力線、統計。

替代方案：需求文件的 `scripts/01_…` 至 `05_…` 編號腳本——解析器需在多支腳本間共用並被測試匯入，套件形式較乾淨；執行順序改由 Makefile 表達。

### 專案根目錄即 repo 根目錄

需求文件的 `taiwan-power-map/` 結構直接展開在 repo 根目錄，不多包一層。

### 原始與中間資料不進 git，processed 輸出進 git

`data/raw/` 與 `data/interim/` 加入 `.gitignore`；`data/processed/` 進 git，作為備份並供下一個 change 的網頁直接使用。台灣快照檔大小為估計值（未量測，預估數百 MB，下載後以 `ls -lh data/raw/` 確認），無論實際大小都不進 git，故此估計不影響決策。

### 距離與簡化在 EPSG:3826 計算

去重距離（500 m）、電力線簡化容差（10 m）都先投影到 EPSG:3826（TWD97 / TM2 121）計算，輸出再轉回 EPSG:4326。

### 去重採保守規則且參數可調

屋頂型太陽能門檻（預設 1 MW）與同名重複距離（預設 500 m）以命令列參數提供（`--rooftop-threshold-mw`、`--dedup-distance-m`），預設值寫在 Makefile。規則以「寧可保留、不要誤刪」為原則：容量未知的非屋頂 generator 一律保留。

### 多能源設施標為 mixed 並保留全部來源

來源標籤的每個值先正規化成能源類別（`solar`、`wind`、`hydro`、`gas`、`coal`、`nuclear`、`geothermal`，其餘一律 `other`），去重後依出現順序存進 `energy_sources` 陣列。陣列只有一個類別時 `energy` 就是該類別；有兩個以上時 `energy` 為 `mixed`；沒有標籤時為 `unknown`、陣列為空。前端篩選以 `energy_sources` 為準（勾任一來源即顯示），`energy` 只用來決定圖示。

取代本 change 先前「取第一個來源」的做法：OSM 標籤的排列順序是標註者的習慣，不代表主次，以它決定主要能源等於把未經證實的判斷寫進資料。

替代方案：一律歸 `other`——興達、台中等大型多燃料電廠會失去能源資訊，不採用；依電廠內 generator 的容量推算主要能源——台灣 OSM 的 generator 層級資料完整度未知（未量測，2.4 檢查點的多能源筆數可作為判斷依據），留待官方資料 change 再評估。

### 屬性值附帶資料來源欄位

會被官方資料補值的屬性各附一個來源欄位：設施的 `capacity_source`、`energy_data_source`，電力線的 `voltage_source`。值有內容時為 `osm`，值為 `null` 時來源也為 `null`。下一個 change 補值時填入如 `taipower` 的值，OSM 原值不覆蓋。

替代方案：等官方資料 change 再加欄位——會讓網頁與資料結構跟著改兩次，不採用；用巢狀 `provenance` 物件——前端讀取與 GeoJSON 工具相容性較差，採平面欄位。

### 以範圍框限定台灣本島，跨界圖徵整條保留

抽取時保留幾何與「本島範圍框」相交的圖徵，其餘排除。本島範圍框預設為經度 119.9–122.2、緯度 21.8–25.4（依地圖概略取值，非量測；2.4 檢查點以實際排除清單確認沒有誤刪本島圖徵），以 `--main-bbox` 參數提供。這個範圍框不含金門、馬祖、澎湖，包含綠島、蘭嶼、小琉球、龜山島。部分位於範圍框內的圖徵（例如台澎海纜）整條保留、不裁切，符合「不改線」原則。

排除的圖徵依金門、馬祖、澎湖三個範圍框（值見 spec）與「其他」分類計數，寫進抽取摘要與統計。

替代方案：用縣市界或 OSM 海岸線做本島輪廓——能精準切掉綠島、蘭嶼等，但使用者決定保留這些島，範圍框已足夠且不需額外資料；在設施／電力線步驟各自篩選——規則會重複兩份，集中在抽取步驟較單純。

## Implementation Contract

**指令與輸出**

| 指令 | 行為 |
| --- | --- |
| `make data` | 從零產出 `data/processed/` 下四個檔；快照已存在則不重新下載 |
| `make extract` | 只跑下載＋抽取，印出抽取摘要並寫入 `data/interim/extract_summary.json` |
| `make test` | 以 pytest 執行 `tests/` |
| `make clean` | 刪除 `data/interim/` 與 `data/processed/` 內容，保留 `data/raw/` |

**抽取摘要**（`data/interim/extract_summary.json` 與終端輸出內容一致）：快照時間、保留圖徵依 `power` 值 × 幾何類型（Point / LineString / Polygon / MultiPolygon）的數量、無幾何 relation 的數量、多能源（`energy` 為 `mixed`）的 plant／generator 筆數、依金門／馬祖／澎湖／其他分類的排除數量、無效幾何跳過數。

**解析器介面**（`powermap.parsers`，皆為純函式）

- `classify_energy(source: str | None) -> tuple[str, list[str]]`：回傳 `(energy, energy_sources)`，`energy` 為 `solar|wind|hydro|gas|coal|nuclear|geothermal|other|mixed|unknown`
- `parse_capacity_mw(raw: str | None) -> float | None`
- `parse_voltage_max_kv(raw: str | None) -> float | None`
- `classify_voltage(kv: float | None) -> str`：回傳 `ehv|hv|mv|lv|missing`

**資料形狀**：`plants.geojson`、`lines.geojson`、`stats.json` 欄位依各 spec 定義；`dedup_log.csv` 欄位為 `action,kept_osm_id,dropped_osm_id,reason,distance_m`。

**OSM id 規則**：`osm_id` 為 `n|w|r` 前綴加數字 id；pyosmium 面物件的 area id 需換回原始 way / relation id。`osm_url` 為 `https://www.openstreetmap.org/{node|way|relation}/{id}`。

**失敗模式**

- 下載失敗或檔案不完整：`make` 以非零結束碼停止，不產生下游檔案
- pbf header 沒有快照時間：快照時間記為 `null`，終端印出警告，流程繼續
- 單筆圖徵幾何無效：跳過該筆並計數，最後在終端印出跳過數量；不中斷流程

**驗收**

- `make test` 全數通過
- 在刪除 `data/interim/`、`data/processed/` 後，`make data` 成功並產出四個檔
- 抽取摘要已交給使用者確認（人工檢查點）
- 使用者確認去重疑義案例（人工檢查點）
- 需求文件第 8 節中屬於資料面的項目通過（見 tasks）

**範圍邊界**

- 範圍內：下載、抽取、本島範圍篩選、解析、設施整理與去重、電力線整理、資料來源欄位（只填 `osm`）、統計、Makefile、測試、README 的資料管線說明
- 範圍外：任何 `web/` 檔案、縣市界資料、官方資料取得與比對、主要能源判定、金門馬祖澎湖資料、部署

## Risks / Trade-offs

- [OSM 標註不完整且不一致，數量不會與原作相同] → 抽取後先人工確認數量；驗收以原作數量（約 700 設施、約 2,100 段線，來自原作說明，非本專案量測）為參考，差距超過 30%（自訂門檻）時列出可能原因與案例給使用者判斷，而不是自行調整規則
- [離岸風場可能是整場一個 plant，也可能是一支支 generator] → 先依通用規則處理，在驗收時列出離岸風場案例給使用者決定是否另外聚合
- [`mixed` 類別讓興達、台中等大廠沒有單一能源顏色] → `energy_sources` 保留全部來源供篩選與圖示設計；主要能源留待官方資料 change 以有根據的方式補上
- [純數字容量視為 MW 可能誤判小型設施] → 驗收時列出所有純數字容量的案例供抽查
- [本島範圍框是概略值，邊緣可能誤刪或誤留] → 2.4 檢查點列出「其他」類排除圖徵的清單供確認；範圍框可用參數調整
- [只有 OSM 來源，無法證明資料本身正確] → 本 change 只保證處理規則正確；資料正確性由第二個 change 的官方資料交叉驗證負責，網頁上線前完成
- [pyosmium 與 osmium-tool 輸出細節可能不同] → 中間檔欄位固定，下游只依賴欄位約定

## Migration Plan

全新專案，無既有資料需遷移。回滾方式為刪除新增檔案或 revert commit。

## Open Questions

- 離岸風場是否需要額外聚合：待抽取後看實際資料決定（驗收任務中處理）
