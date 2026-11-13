## Context

change 1、2 已經產出網頁要用的資料，以下是 2026-11-13 實測的數字：

| 檔案 | 大小（實測） | 內容 |
| --- | --- | --- |
| `data/processed/plants.geojson` | 921 KB | 1,577 個 Point：`kind=plant` 670 筆、`kind=generator` 907 筆（太陽能 478、風力 404、其他 25） |
| `data/processed/lines.geojson` | 1.14 MB | 2,515 條 LineString，`voltage_class` 分為 ehv 264、hv 649、mv 542、lv 1、missing 1,059 |
| `data/processed/stats.json` | 1.2 KB | 快照時間、各類數量、缺值數，以及 `official.unmatched.no_osm`（47） |
| `data/processed/official_diff.csv` | 0.4 KB | 6 座容量差距超過門檻的電廠：`official_id,osm_id,osm_capacity_mw,official_capacity_mw,diff_ratio` |

其他已知事實：

- 資料只涵蓋台灣本島與鄰近島嶼（含綠島、蘭嶼），金門、馬祖、澎湖已在抽取階段排除（`osm-power-extraction` 規格的 Main island scope filter）。
- `energy` 共 10 類（solar、wind、hydro、gas、coal、nuclear、geothermal、other、mixed、unknown）。`mixed` 有 3 筆；README 已經規定篩選要以 `energy_sources` 為準。
- 縣市界資料集是 data.gov.tw 7442「直轄市、縣市界線(TWD97經緯度)」，授權為政府資料開放授權條款第 1 版。SHP 版的下載網址是 `https://www.tgos.tw/tgos/VirtualDir/Product/1cd4f4c9-6b01-4cf9-bf6c-23a73aa17d24/直轄市、縣(市)界線1140318.zip`，大小 3,762,381 bytes（2026-11-13 以 HTTP HEAD 實測）。
- GitHub repo `SweetCowCow/PowerMap` 目前是 private，預設分支是 `main`。全部 14 個 commit 的作者 email、以及 `docs/spectra/changes/archive/*/.openspec.yaml` 和本 change 的 `.openspec.yaml` 裡的 `created_by`／`archived_by`，都是公司 email。repo 的 git 設定 `user.email` 也是公司 email。
- 開發機有 Node v26，沒有 `git-filter-repo`，但可以用 `uvx git-filter-repo` 執行。

## Goals / Non-Goals

**Goals:**

- 一個不需要打包工具的單頁地圖，桌機和手機都能操作
- 篩選、Popup、統計面板忠實呈現資料，包括缺值
- 不使用外部圖磚也能看出台灣的輪廓
- push 到 `main` 後自動發佈到 GitHub Pages
- 公開 repo 之前，git 歷史裡沒有公司 email

**Non-Goals:**

- 不修正風力約 15 座官方電廠的對照表，也不幫 32 座對不到的官方電廠查座標或加估計位置圖層（列為 change 4）
- 不顯示金門、馬祖、澎湖，也不做跳轉鈕（資料不涵蓋）
- 不改變資料管線既有輸出的欄位或數值
- 不做即時發電資料、運轉狀態（除役）標示、變電所圖層
- 不做 Matplotlib 靜態海報
- 不做自訂網域、不加網站分析或追蹤碼
- 不做變電所圖層（另開 change 4）
- 不做「我的位置」定位（使用者沒有選）
- 不做 Esri 影像

## Decisions

### 純 HTML/JS 加 CDN，邏輯集中在可測試的 lib.js

`web/index.html` 用 CDN 載入 Leaflet 1.9.4 和 Leaflet.markercluster 1.5.3（含 SRI integrity）。`web/lib.js` 放純函式，例如樣式對應、篩選判斷、Popup 內容、計數和 CSV 解析，不碰 DOM 和 Leaflet；`web/app.js` 負責 DOM、Leaflet 和事件。`lib.js` 用 ES module 寫，瀏覽器和 `node --test` 都能直接載入。

替代方案有兩個：用 Vite 打包，但計畫明訂不需要打包工具，部署也會多一步 build；或是邏輯全部寫在 `app.js`，但那樣篩選和缺值顯示就沒辦法做單元測試。這兩個都不採用。

### 設施用 canvas circleMarker，核能用菱形 DivIcon

地圖開 `preferCanvas: true`，電廠、發電機、線段都畫在 canvas 上。核能設施只有 4 筆，要畫成白色空心菱形，而 canvas circleMarker 畫不出菱形，所以改用 `L.marker` 搭配 DivIcon（內嵌 SVG）。`mixed` 用「其他」的紫色 `#b98ad9` 填色，外框畫成白色虛線（`dashArray: "2 2"`），圖例另外列一行。

電廠和發電機用不同半徑（電廠 5 px、發電機 3 px），只用來分辨種類，不代表容量；圖例會寫明這點。

### 發電機依能源分組聚合，電廠不聚合

每個 `energy` 值各建一個 `L.markerClusterGroup`，只放 `kind=generator` 的設施。聚合點用 `iconCreateFunction` 產生固定 28 px 的圓形 DivIcon，底色是該能源的顏色，中間寫聚合的發電機數。`disableClusteringAtZoom: 12`，`maxClusterRadius: 40`。`kind=plant` 放在一般的 layer group，不聚合。

替代方案有兩個：所有發電機共用一個聚合群組，但聚合點會混合能源，失去顏色，預設的大小又會隨數量變大，容易被誤讀成容量；或是完全不聚合，但全台視角下風機會沿海岸擠成一條線。這兩個都不採用。

### 能源篩選以 energy_sources 為準，mixed 不是獨立勾選項

能源勾選框共 9 個：solar、wind、hydro、gas、coal、nuclear、geothermal、other、unknown。一筆設施在下面兩種情況會顯示：

- `energy_sources` 中至少有一個類別被勾選
- `energy_sources` 是空陣列（即 `energy=unknown`），而且 unknown 被勾選

所以 `coal;gas` 的 mixed 電廠，只要勾選煤或氣其中一個就會出現。這和 README 的資料原則「篩選時以 `energy_sources` 為準」一致，也避免網頁替 mixed 決定主要能源。

### 只看資料缺口是額外的交集條件

「只看資料缺口」開啟時，只顯示 `missing_capacity=true` 的設施和 `missing_voltage=true` 的線，同時仍然套用能源和電壓篩選。關閉時則不限制。

### Popup 與統計面板的資料來源

- 設施 Popup 顯示：名稱（缺值顯示「未命名」）、種類（電廠／發電機）、能源、容量（缺值顯示「未填」）、容量來源（`capacity_source`：`osm` 顯示「OSM」、`taipower` 顯示「台電官方補值」）、官方主要能源（`energy_primary`，有值才顯示）、營運者（缺值顯示「未填」）、OSM 連結。電廠另外顯示 `n_generators`。
- 容量差距：`make web` 會把 `official_diff.csv` 一起複製到 `web/data/`，網頁載入後用 `lib.js` 解析，依 `osm_id` 對應。有對應的設施，在 Popup 顯示「台電官方容量 X MW，與 OSM 差 Y%」。這樣不需要修改資料管線的輸出欄位。
- 線段 Popup 顯示：種類（line／minor_line／cable）、最高電壓（缺值顯示「未填」）、原始 `voltage_raw`、`location`（有值才顯示）、OSM 連結。
- 統計面板：資料快照時間、目前顯示的設施數和線段數（分母是總數），以及缺容量、缺電壓、對不到 OSM 的官方電廠數（`stats.official.unmatched.no_osm`）。「目前顯示」是依篩選條件逐筆計算，不是畫面上的聚合點數。

### 縣市界由資料管線下載簡化並進 git

新增 `powermap/boundaries.py` 和 `make boundaries`，需要連網，不屬於 `make data` 的流程。步驟如下：

1. 下載 SHP zip 到 `data/raw/boundaries/`（gitignore，已存在就跳過）
2. 用 geopandas 讀取，排除澎湖縣、金門縣、連江縣
3. 轉到 EPSG:3826，用 100 m 容許誤差簡化（保留拓樸），再轉回 EPSG:4326，座標四捨五入到小數 5 位
4. 每個縣市輸出一筆 Feature，只保留 `name` 屬性

輸出 `data/processed/counties.geojson` 並 commit。檔案頂層加上 `source` 物件，記錄資料集編號、網址、下載時間、原始 zip 的 SHA-256 和授權。

排除三個離島縣市，是因為資料不涵蓋它們，留著輪廓會讓人誤以為那裡沒有發電設施。替代方案有兩個：網頁執行時直接抓 TGOS（會依賴外部服務，而且 SHP 不能直接在瀏覽器讀）；或是把原始 zip 也 commit（3.7 MB 的二進位檔，而輸出檔已經足以重現網頁）。這兩個都不採用。

### 底圖預設縣市界，深色圖磚為可切換圖層

背景色 `#0b1826`。縣市界用陸地色 `#142534` 填色、`#22384a` 描邊，放在預設的 base layer「縣市界（離線）」。另外提供 base layer「深色圖磚」（CARTO dark_all，標示 © OpenStreetMap contributors © CARTO）。兩者用 Leaflet layers control 切換。

### 外部圖磚改用 OSM 標準圖磚並以 CSS 調暗

**Supersedes**: build-web-map / 底圖預設縣市界，深色圖磚為可切換圖層

預設底圖仍是「縣市界（離線）」。可切換的外部圖磚改為 OSM 標準圖磚（`https://tile.openstreetmap.org/{z}/{x}/{y}.png`，`maxZoom: 19`），圖層名稱「OSM 圖磚（調暗）」，標示 © OpenStreetMap contributors，並移除 CARTO。OSM 標準圖磚是淺色的，所以在這個圖層的 tile 元素上套用 CSS filter（`invert(1) hue-rotate(180deg) brightness(0.85) contrast(0.9)`，數值在實作時以截圖調整），讓它和深色介面一致；filter 只套用在圖磚上，不影響電力圖層的顏色。

原因：使用者實際開啟網站時，CARTO 圖磚只回傳一張「需要 API key」的圖片，看不到地圖；原本以為 CARTO 不需要 key 的判斷，只檢查了請求有沒有回應，沒有檢查圖磚內容（2026-11-13）。OSM 圖磚依 OSM Tile Usage Policy 只適合低流量，這個網站只把它當選用圖層，預設不載入。替代方案有三個：保留 CARTO 再加 OSM；只用 OSM 但不調暗（和深色介面對比太強）；維持只用 CARTO。使用者都沒有選。

### 側欄以電力線為主，能源預設不勾

側欄順序改為：標題 → 統計（電力線排在設施前）→ 電力線電壓（預設全勾）→ 只看資料缺口 → 能源（預設全部不勾，含全選／全不選）→ 說明與來源。打開頁面時只看到電力線，設施要自己勾選才會出現。手機抽屜收合時的摘要也改成電力線在前。

原因：使用者主要想看各地的電力線狀況（2026-11-13）。

### 底圖增加原色 OSM 與國土測繪中心正射影像

底圖改為四個選項，依序為：縣市界（離線，預設）、OSM 圖磚（調暗）、OSM 圖磚（原色）、正射影像（國土測繪中心）。

- 原色 OSM 和調暗版用同一組圖磚網址，只是不加 `osm-dim` class。
- 正射影像用國土測繪中心 WMTS：`https://wmts.nlsc.gov.tw/wmts/PHOTO2/default/GoogleMapsCompatible/{z}/{y}/{x}`。注意網址中是先 y 再 x。標示「正射影像 © 內政部國土測繪中心」，授權為政府資料開放授權條款第 1 版。

2026-11-13 實測：PHOTO2 和 Esri World Imagery 都回傳真正的影像，下載台北 z13 的圖磚並人工檢視確認。採用 PHOTO2，因為它是政府開放資料、授權清楚，台灣解析度高。Esri World Imagery 授權條款較模糊，不採用。PHOTO2 在台灣以外沒有影像，但本網站只涵蓋台灣。

### 定位工具放在地圖上方

地圖左上角（縮放鈕右側）放一個定位列，手機版放在畫面頂端，包含：

- **縣市快速切換**：下拉選單列出 `counties.geojson` 的 19 個縣市，選取後 `fitBounds` 到該縣市範圍。不需要外部服務。
- **搜尋框**：輸入時，即時比對本地設施的 `name`（不分大小寫，包含即算），列出最多 8 筆電廠或發電機，只顯示有名稱的。選取後地圖移到該設施（zoom 15），並在該點開啟 Popup。即使該設施因能源篩選而隱藏，也會用獨立的 `L.popup` 顯示，並畫一個暫時的高亮圓圈。
- **地名或地址搜尋**：按 Enter 或「搜尋地名」按鈕時，才向 OSM Nominatim 查詢（`https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=tw&accept-language=zh-TW&limit=5&q=...`），列出最多 5 筆結果，選取後 `fitBounds` 到結果的 `boundingbox`。
  - 依 Nominatim 使用政策，不做邊打字邊查詢，兩次查詢至少相隔 1 秒，並標示「地名搜尋：© OpenStreetMap contributors（Nominatim）」。
  - 搜尋框下方註明輸入的文字會送到 Nominatim。
  - 查詢失敗或沒有結果時，在結果區顯示明確訊息（例如「找不到『xxx』，請換個關鍵字」或「地名搜尋暫時無法使用」），不跳出 alert。

設施名稱比對和 Nominatim 網址組裝寫在 `lib.js`（`searchFacilities(features, query, limit)`、`nominatimUrl(query)`），用 `node --test` 測試。地圖操作和 fetch 留在 `app.js`。

替代方案：用 Leaflet 外掛（例如 leaflet-control-geocoder），會多一個 CDN 依賴，而且很難和本地設施搜尋整合在同一個搜尋框，所以不採用。

### make web 只複製檔案，不觸發資料管線

`make web` 是 phony 目標，它的 recipe 只會建立 `web/data/`，並複製 `plants.geojson`、`lines.geojson`、`stats.json`、`official_diff.csv`、`counties.geojson`。它**不**把資料管線的輸出列為 prerequisite；否則在 CI 上，Makefile 的參數戳記機制會把輸出檔回溯成舊時間，進而觸發完整的資料管線（CI 上沒有 OSM 快照）。來源檔缺少時，`cp` 會失敗並回傳非 0。`make all` 改成 `data web`。`web/data/` 加進 `.gitignore`。

### 網頁單元測試用 node --test

新增 `web/tests/lib.test.js`，用 Node 內建的 `node:test` 和 `node:assert`，不需要 `package.json` 和任何 npm 套件。`make test-web` 執行 `node --test web/tests/`。`make test` 維持只跑 pytest，CI 另外執行 `make test-web`。

### GitHub Actions 發佈到 Pages

新增 `.github/workflows/pages.yml`：在 `push` 到 `main` 和 `workflow_dispatch` 時觸發。步驟依序為 `actions/checkout`、`actions/setup-node`（Node 22）、`make test-web`、`make web`、`actions/configure-pages`、`actions/upload-pages-artifact`（path: `web`）、`actions/deploy-pages`。權限為 `pages: write`、`id-token: write`、`contents: read`，並設定 `concurrency: pages`。

CI 不跑 Python 資料管線，因為 processed 的輸出檔已經 commit。替代方案是發佈到 `gh-pages` 分支，但那樣 repo 會多一個充滿產出檔的分支，所以不採用。

### 公開前用 git-filter-repo 改寫公司 email

步驟如下：

1. 先用 `git bundle create` 備份到 scratchpad
2. 用 `gh api user` 取得帳號 id，組出 `<id>+SweetCowCow@users.noreply.github.com`
3. 執行 `uvx git-filter-repo --mailmap`，替換 author 和 committer email，並用 `--replace-text` 替換所有 blob 裡的公司 email（涵蓋歷史中的 `.openspec.yaml`）
4. 工作目錄中尚未 commit 的 `.openspec.yaml`（本 change 的）也要替換
5. repo 的 `git config user.email` 改成 noreply 信箱
6. 驗證 `git log --all --format='%ae %ce'` 和 `git grep` 所有 commit 都找不到公司網域

filter-repo 會移除 `origin`，要重新加回。**force push 和 `gh repo edit --visibility public` 之前，必須先向使用者確認**，確認後依序執行。

替代方案有兩個：開一個全新的 public repo（會失去歷史）；或是保留公司 email（使用者已經拒絕）。這兩個都不採用。

## Implementation Contract

**行為**

- 執行 `make boundaries` 後，`data/processed/counties.geojson` 包含本島與鄰近島嶼所屬的 19 個縣市（22 個縣市扣掉澎湖、金門、連江；數量在任務中實測確認），每筆 Feature 只有 `name` 屬性，頂層有 `source` 物件。檔案應小於 1 MB（估計值，由任務實測確認）。
- 執行 `make web` 後，`web/data/` 有五個檔案；任一來源檔缺少時，指令失敗且回傳非 0。
- 用 `python -m http.server -d web` 開啟網頁時：
  - 初始視角是台灣本島；預設底圖是縣市界，不發出任何圖磚請求。
  - 側欄依序為電壓篩選、「只看資料缺口」、能源篩選；5 個電壓勾選框預設全勾，9 個能源勾選框（含全選／全不選）預設全部不勾，所以初始畫面只有電力線、設施數為 0。所有控制項都會即時改變地圖和統計面板的「目前顯示」數量。
  - zoom < 12 時，發電機以各能源顏色的固定大小聚合點顯示；zoom ≥ 12 時，逐支顯示。
  - 點擊設施或線段會出現 Popup，缺值顯示「未填」或「未命名」，不顯示 `null`、`0` 或空白。
  - 頁尾顯示快照時間（來自 `stats.snapshot`）、OSM ODbL 授權、政府資料開放授權條款第 1 版，以及「本圖不是即時供電圖；設施存在不等於運轉中；圓點大小不代表容量、線寬不代表潮流」。
  - 視窗寬度 < 768 px 時，側欄改成底部抽屜，可以展開和收合。
- push 到 `main` 後，Actions 會執行 `make test-web` 和 `make web`，並發佈到 `https://sweetcowcow.github.io/PowerMap/`。

**資料形狀**

- `lib.js` 匯出：`ENERGY_COLORS`、`VOLTAGE_STYLES`、`facilityVisible(props, filters)`、`lineVisible(props, filters)`、`facilityPopupHtml(props, diff)`、`linePopupHtml(props)`、`parseDiffCsv(text)`（回傳以 `osm_id` 為鍵的 Map）、`countVisible(features, predicate)`、`formatCapacity(mw)`。
- `filters` 的形狀：`{ energies: Set<string>, voltages: Set<string>, gapsOnly: boolean }`。

**失敗模式**

- Nominatim 查詢失敗、逾時或沒有結果時，在搜尋結果區顯示明確訊息，地圖不移動。

- 任一資料檔 fetch 失敗時，在地圖上方顯示錯誤橫幅，寫出失敗的檔名，不顯示空白地圖。
- `official_diff.csv` 載入失敗不阻擋頁面，Popup 只是不顯示差距。
- Popup 中的字串（名稱、營運者等來自 OSM 的文字）必須經過 HTML escape。

**驗收**

- `make test-web` 全部通過，涵蓋：mixed 篩選、unknown 篩選、缺口模式交集、缺值顯示「未填」、HTML escape、CSV 解析、容量格式化。
- `uv run pytest` 全部通過，含 `tests/test_boundaries.py`（排除離島縣市、只保留 `name`、座標位數、`source` 欄位）。
- 用 Chrome DevTools 在桌機（1280×800）和手機（390×844）尺寸各截一張圖人工檢查，console 沒有錯誤。
- `git log --all --format='%ae %ce' | grep -c <公司網域>` 的結果為 0。

**範圍**

- 範圍內：`web/` 全部、`powermap/boundaries.py`、Makefile 的 `boundaries`、`web`、`test-web`、`all` 目標、`.github/workflows/pages.yml`、README 和 `.gitignore`、改寫 git 歷史、切換 repo 公開、啟用 Pages。
- 範圍外：資料管線既有模組（extract、facilities、enrich、lines、stats）的行為、`crosswalk.csv`、官方電廠的估計座標。

## Risks / Trade-offs

- [改寫歷史後 commit hash 全部改變，`handoff.md` 和已封存 change 文件中引用的 hash 會失效] → 改寫後更新 `handoff.md`；已封存文件中的 hash 只是歷史紀錄，不改。改寫前先做 bundle 備份，可以還原。
- [force push 後，其他電腦上的 clone 會和遠端分歧] → 目前只有使用者一人使用；切換前提醒使用者，其他 clone 要重新 clone。
- [公開後，未來 commit 可能誤帶公司資料] → repo 的 git email 改成 noreply；之後每次 commit 前，都要檢查有沒有公司相關內容。
- [CDN 或 OSM 圖磚伺服器停止服務或限制流量] → 預設底圖是本地縣市界，OSM 圖磚只是選用圖層；Leaflet 和 markercluster 用固定版本加 SRI。
- [canvas 和 DivIcon 混用時，聚合點的 DOM 數量過多] → 聚合點只在 zoom < 12 出現，數量受 `maxClusterRadius` 限制；用 DevTools 效能面板檢查平移時沒有明顯卡頓。
- [TGOS 下載網址含版本日期，之後可能失效] → 網址寫成可覆寫的常數（`BOUNDARY_URL`）；輸出檔已經 commit，網頁不受影響。

## Migration Plan

1. 先在本機完成網頁和 `make boundaries`，所有測試通過後 commit（此時 repo 仍是 private）。
2. 改寫 git 歷史並驗證，**向使用者確認後**才 force push。
3. **向使用者確認後**，才把 repo 改成 public，接著把 Pages 的來源設成 GitHub Actions（`gh api -X POST repos/SweetCowCow/PowerMap/pages -f build_type=workflow`）。
4. 觸發 workflow，確認網站可以開啟。

回溯方式：Pages 可以用 `gh api -X DELETE repos/SweetCowCow/PowerMap/pages` 關閉；repo 可以改回 private（但公開期間被抓走的內容無法收回）；歷史可以從 bundle 還原。

## Open Questions

- `handoff.md` 目前還沒進 git，內容含本機路徑和工作筆記。repo 公開前，要請使用者決定要 commit 它還是加進 `.gitignore`（列在任務中詢問）。
