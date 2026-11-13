## Context

- `powermap/osm.py` 的 `POWER_VALUES` 目前是 `plant`、`generator`、`line`、`minor_line`、`cable`。`extract.py` 只對 `FACILITY_VALUES`（`plant`、`generator`）組裝面，並用它判斷 mixed 能源。
- 規格 `osm-power-extraction` 明文排除 `substation`（「Substation is excluded」情境），`tests/test_extract.py` 的 `test_substation_is_excluded` 也在檢查這件事。
- 電壓解析 `parse_voltage_max_kv` 和分級 `classify_voltage` 在 `powermap/parsers.py`，電力線已經在用。
- 設施的點位是取面的 `representative_point()`，名稱是 `name`，沒有時改用 `name:zh`（`powermap/facilities.py`）。
- 2026-11-13 實測 OSM 快照中的變電所（全台，套用本島篩選前）：共 791 個（way 737、relation 53、node 1）；有 voltage 440 個；有名稱 650 個。`substation` 種類：distribution 288、未標 281、transmission 80、minor_distribution 68、transition 22、industrial 22、yes 13、traction 11。

## Goals / Non-Goals

**Goals:**

- 變電所進入資料管線，數量、缺值都可追溯
- 地圖上可以把變電所和電力線一起看，用同一套電壓配色
- 既有的設施和電力線輸出完全不變

**Non-Goals:**

- 不做變電所去重（例如同一個變電所同時有 way 和 relation），保留每個 OSM 物件，數量依實際輸出為準
- 不做電塔（`power=tower`）
- 不推算變電所和電力線的連接關係，也不補畫連線
- 不用官方資料補變電所的電壓（目前沒有官方變電所資料）
- 不改官方電廠座標（change 5）

## Decisions

### 抽取時把 substation 當成可組成面的類型

`POWER_VALUES` 加入 `substation`，新增 `AREA_VALUES = ("plant", "generator", "substation")`，用在 osmium 的 area 組裝 TagFilter 和封閉 way 的判斷。`FACILITY_VALUES` 維持只有 `plant` 和 `generator`，所以 mixed 能源計數不受影響。

`extract_summary.json` 的 `excluded_by_power` 會自動多一個 `substation` 鍵，因為它是由 `POWER_VALUES` 產生的。

替代方案是另外寫一個只抽變電所的步驟，但那樣要讀兩次 pbf，本島範圍篩選的邏輯也要重複，所以不採用。

### 變電所資料集沿用設施的點位與電力線的電壓邏輯

新增 `powermap/substations.py`：讀 `power.geojsonseq` 中 `power=substation` 的 Feature，面取 `representative_point()`，點直接用，座標四捨五入到小數 5 位。輸出 `data/processed/substations.geojson`，每個 Feature 的屬性依序為：

| 欄位 | 內容 |
| --- | --- |
| `osm_id`、`osm_url` | 例如 `w123`、OSM 網址 |
| `name` | `name`，沒有時用 `name:zh`，都沒有為 `null` |
| `operator` | `operator` 或 `null` |
| `substation` | `substation` 標籤原值或 `null` |
| `voltage_max_kv`、`voltage_raw`、`voltage_class`、`voltage_source`、`missing_voltage` | 和電力線相同的規則 |
| `geom_src` | 原始幾何類型（Polygon、MultiPolygon、Point） |

Feature 依 `osm_id` 排序，讓輸出穩定。

### stats.json 新增變電所欄位，不改既有欄位

新增 `substations`、`substations_missing_voltage`、`substations_by_voltage_class`（5 級都列出，沒有的為 0），終端摘要也印出這三項。既有欄位的值不變。

### 變電所圖層畫成依電壓著色的方形 DivIcon

Leaflet 的 canvas circleMarker 畫不出方形，所以改用 `L.marker` 加 DivIcon（8 px 方形），放在介於電力線和設施之間的獨立 pane。有電壓的用 `VOLTAGE_STYLES` 的顏色實心填色；缺電壓的用 `#8a94a0` 外框的空心方形。預估數量是數百個（本島篩選後的實際數字以 `stats.json` 為準），DOM 元素的數量在可接受範圍；任務中會用 DevTools 檢查平移縮放時沒有明顯卡頓。

替代方案是自訂 canvas 方形 renderer，效能較好，但要擴充 Leaflet 內部 API，所以不採用。

### 變電所跟著電壓篩選和資料缺口一起開關

一個變電所顯示的條件是三者同時成立：

- 「變電所」開關開啟（預設開啟）
- 它的 `voltage_class` 有被勾選
- 「只看資料缺口」開啟時，它的 `missing_voltage` 為 true

判斷寫在 `lib.js` 的 `substationVisible(props, filters)`，`filters` 新增 `substations: boolean`。「變電所」開關放在電壓篩選區塊的最下方，圖例顯示方形符號。

### Popup、搜尋與統計

- Popup 用 `lib.js` 的 `substationPopupHtml(props)`，標題是名稱（缺值顯示「未命名變電所」），列出種類、最高電壓（缺值顯示「未填」）、原始 voltage、營運者（缺值顯示「未填」）和 OSM 連結。
- 種類的中文對照：transmission 輸電、distribution 配電、minor_distribution 小型配電、transition 架空與地下轉接、industrial 工業用、traction 鐵路供電、converter 換流；其他值顯示原文，`null` 或 `yes` 顯示「未填」。
- 搜尋框的本地結果分成「發電設施」和「變電所」兩組，各最多 8 筆，都用 `searchFacilities` 比對名稱。
- 統計區塊「目前顯示」加上「座變電所」（目前數 / 總數）；「全部資料」加上「缺電壓的變電所」。

### make web 多複製一個檔案

`WEB_FILES` 加入 `data/processed/substations.geojson`，網頁把它列為必要檔案；缺少時和其他必要檔案一樣顯示錯誤橫幅。

### 電力線與設施共用一張 canvas，變電所圖層放在最上層

**Supersedes**: add-substations / 變電所圖層畫成依電壓著色的方形 DivIcon

方形 DivIcon 的做法不變，只改圖層順序。review 實測（2026-11-13）：Leaflet 的每個 canvas renderer 都會產生一張蓋滿地圖的 canvas，而且會攔下點擊。原本電力線（410）和設施（420）各用一張 canvas，變電所放在中間（415），結果只要開過一次發電設施，下面的變電所和電力線就都點不到（電力線的問題從 change 3 就存在，但當時設施預設不顯示，驗證時沒抓到）。

改法：電力線和設施共用一個 canvas renderer（pane `vectors`，z 410）。`apply()` 每次都先加電力線、再加設施，所以設施畫在上面，點擊也由同一張 canvas 判斷。變電所 pane 改到 z 430，因為它是一個個小方塊元素，pane 本身沒有面積，不會擋住下面的點擊。

### 電壓勾選框同時顯示線段數和變電所數

電壓勾選框同時控制線和變電所，所以每一列的數字改成「N 段・M 座」（線段數取 `stats.by_voltage_class`，變電所數取 `stats.substations_by_voltage_class`），避免讀者以為數字只有一種。

### 部署時為網頁檔案加上版本號

GitHub Pages 對所有檔案都設定快取 10 分鐘。部署後，瀏覽器可能拿到新的 `index.html` 和舊的 `app.js`（實測時發生過多次），新舊混搭就會出錯。GitHub Actions 在 `make web` 之後，把 `index.html` 裡的 `app.js`、`style.css`，以及 `app.js` 裡 import 的 `./lib.js` 都加上 `?v=<commit 前 7 碼>`。原始檔不變，本機預覽不受影響。

### 重複抽查結果

2026-11-13 對 788 個變電所的抽查結果：
- 沒有同名的 way 和 relation。
- 任兩點距離在 150 m 內的有 51 對（任何類型都算）。抽看的例子多半是電廠或廠區內相鄰的開關場、配電室，例如 `r3442741`（緊急發電機）和 `w256835088`（變電站）只差約 10 m，但名稱不同。
- verify 另外算出：53 個 relation 中，有 11 個在 150 m 內有某個 way 的代表點，可能是重複，但沒有逐筆確認。

依「不做去重」的決定，這次照實輸出。如果之後要去重，可以從這 11 組 relation 開始逐筆確認。

## Implementation Contract

**行為**

- `make data` 後，`data/processed/substations.geojson` 存在，數量等於 `power.geojsonseq` 中 `power=substation` 的 Feature 數；`stats.json` 有 `substations`、`substations_missing_voltage`、`substations_by_voltage_class`，而且 `substations_by_voltage_class` 的總和等於 `substations`。
- 重跑後 `plants.geojson` 和 `lines.geojson` 和重跑前完全相同（用 `git diff --exit-code` 確認）；`stats.json` 中既有欄位只有 `built_at` 和 `excluded_outside_main_island` 改變。後者計算的是所有被排除的 OSM 原始圖徵，現在包含本島以外的變電所（2026-11-13 實測：penghu 從 57 變成 60，其他區域不變）。
- 網頁預設顯示所有變電所；取消勾選某個電壓分級時，該分級的線和變電所一起隱藏；關閉「變電所」開關時，所有變電所隱藏，線不受影響；開啟「只看資料缺口」時，只剩缺電壓的變電所。

**資料形狀**

- `substations.geojson` 的欄位如上表；Point 幾何、座標小數 5 位。
- `lib.js` 新增：`substationVisible(props, filters)`、`substationPopupHtml(props)`、`SUBSTATION_TYPE_LABELS`；`initialFilters()` 回傳值新增 `substations: true`。

**失敗模式**

- `power.geojsonseq` 中沒有變電所時，輸出空的 FeatureCollection，統計為 0，不報錯。
- 網頁載入不到 `substations.geojson` 時顯示錯誤橫幅，寫出檔名。

**驗收**

- `uv run pytest` 和 `make test-web` 全部通過，新增的測試涵蓋：抽取變電所面和點、塔仍然排除、變電所屬性和排序、統計欄位、`substationVisible` 範例表、Popup 缺值和種類對照。
- 用 DevTools 在 1280×800 和手機寬度截圖檢查，console 沒有錯誤；平移縮放時沒有明顯卡頓。
- GitHub Pages 部署成功，正式網址可以看到變電所。

**範圍**

- 範圍內：抽取、變電所資料集、統計、Makefile、網頁圖層與控制、README。
- 範圍外：設施和電力線的處理邏輯、官方資料、變電所去重、電塔。

## Risks / Trade-offs

- [同一個變電所可能同時有 way 和 relation，造成重複] → 不去重，數量照實輸出；任務中抽查重複情形並記錄數量，必要時另開 change 處理。
- [變電所 DivIcon 數量多時，平移變慢] → 任務中用 DevTools 檢查；如果卡頓明顯，改成 zoom 較小時隱藏，或換成 canvas renderer，並先回報再改。
- [抽取規則改動會觸發完整重跑，可能意外改到設施或線] → 用 `git diff --exit-code data/processed/plants.geojson data/processed/lines.geojson` 確認不變。

## Migration Plan

本機跑 `make data` 和 `make web`，測試通過後 commit 資料和程式，push 後由 GitHub Actions 部署。回溯方式是 revert 該 commit。

## Open Questions

（無）
