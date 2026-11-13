## 1. 縣市界資料

- [x] 1.1 依「縣市界由資料管線下載簡化並進 git」實作 Boundary download、Boundary simplification and scope、Boundary output with provenance：新增 `powermap/boundaries.py` 和 `make boundaries`（`BOUNDARY_URL` 可覆寫）。zip 已存在就跳過下載；下載失敗時非 0 退出，且不留下半成品；輸出時排除澎湖縣、金門縣、連江縣，用 100 m 簡化，座標保留 5 位小數，每筆只留 `name`，頂層寫入 `source`。`make data` 不會執行這一步。驗證：`tests/test_boundaries.py` 用小型合成 SHP 和 `file://` 網址，測試排除三縣、只有 `name` 屬性、座標位數、`source.sha256`、已存在時跳過、HTTP 失敗不留檔；`uv run pytest` 全部通過。
- [x] 1.2 [after: 1.1] 執行 `make boundaries` 取得真實資料，確認輸出 19 個縣市（預期值，以實際輸出為準）、檔案小於 1 MB（估計值，以 `ls -l` 實測），並 commit `data/processed/counties.geojson`。驗證：`git check-ignore` 確認 zip 被忽略、`git ls-files` 列出 `counties.geojson`，並記錄實測的大小和縣市數。

## 2. 建置與測試框架

- [x] 2.1 依「make web 只複製檔案，不觸發資料管線」實作 Static site build：新增 phony 目標 `make web`，複製五個檔案到 `web/data/`；`make all` 改成 `data web`；把 `web/data/` 加進 `.gitignore`。驗證：先把 `data/processed/plants.geojson` 的時間改成 2000 年、移走 OSM 快照，再執行 `make web`，確認只執行 cp、沒有執行 uv；暫時改名 `counties.geojson` 後，確認 `make web` 非 0 退出。
- [x] 2.2 依「網頁單元測試用 node --test」實作 Web unit tests：新增 `make test-web`（`node --test web/tests/`）和一個可以執行的 `web/tests/lib.test.js` 骨架，不使用 `package.json`。驗證：`make test-web` 退出 0，`ls web` 沒有 `package.json` 和 `node_modules`。

## 3. 網頁邏輯（lib.js）

- [x] 3.1 [after: 2.2] 依「純 HTML/JS 加 CDN，邏輯集中在可測試的 lib.js」、「能源篩選以 energy_sources 為準，mixed 不是獨立勾選項」和「只看資料缺口是額外的交集條件」，在 `web/lib.js` 實作 Energy filter、Voltage filter and line styles（`VOLTAGE_STYLES`、`lineVisible`）、Data gap mode 的判斷函式（`facilityVisible`、`lineVisible`、`countVisible`）和 `ENERGY_COLORS`。驗證：`web/tests/lib.test.js` 涵蓋 web-map 規格中能源篩選的 5 列範例和缺口模式的 5 列範例，`make test-web` 全部通過。
- [x] 3.2 [after: 3.1] 依「Popup 與統計面板的資料來源」實作 Facility and line popups 的內容函式：`facilityPopupHtml`、`linePopupHtml`、`parseDiffCsv`、`formatCapacity`，含 HTML escape 和「未命名」「未填」的缺值顯示。驗證：測試涵蓋三個欄位都是 null 的設施、嘉惠 `w507020797` 顯示「台電官方容量 1,210 MW」和「差 44.6%」、名稱 `<b>x</b>` 被跳脫，並斷言輸出不含 `null` 或 `undefined`；`make test-web` 通過。

## 4. 網頁畫面（index.html、app.js、style.css）

- [x] 4.1 [after: 1.2, 2.1, 3.1] 實作 Map data loading 和 Base layers，依「底圖預設縣市界，深色圖磚為可切換圖層」：`web/index.html` 用 CDN 載入 Leaflet 1.9.4 和 Leaflet.markercluster 1.5.3（含 SRI），`app.js` 平行 fetch 五個檔案，失敗時用橫幅列出檔名（`official_diff.csv` 失敗則不顯示橫幅）；預設底圖是縣市界，可切換 CARTO 深色圖磚，初始視角是本島。驗證：`make web` 後執行 `python -m http.server -d web`，用 Chrome DevTools 確認預設狀態下沒有 CARTO 請求；暫時改名 `web/data/lines.geojson` 後，確認橫幅會顯示這個檔名。
- [x] 4.2 [after: 4.1] 依「設施用 canvas circleMarker，核能用菱形 DivIcon」和「發電機依能源分組聚合，電廠不聚合」實作 Facility symbols 和 Generator clustering by energy，並畫出依電壓分級的線段樣式（Voltage filter and line styles 的樣式部分）。驗證：用 DevTools 在 zoom 8 確認風力聚合點是 `#6fe0c0`、大小固定且顯示數字；zoom 12 時每支發電機都逐一顯示；核能是白色空心菱形；mixed 有虛線外框；缺電壓的線是虛線。
- [x] 4.3 [after: 3.2, 4.2] 把篩選、Popup 和統計面板接到畫面上：實作 Energy filter、Voltage filter and line styles、Data gap mode 的控制項（含全選／全不選）、Facility and line popups、Statistics panel，以及 Legend and footer（圖例和篩選合一、說明大小與線寬的意義、頁尾列出授權、快照時間和非即時聲明）。驗證：用 DevTools 操作，取消勾選風力後，「目前顯示」的設施數等於 1,577 減去 `energy_sources` 只有 wind 的設施數；開啟缺口模式後，設施數等於 `missing_capacity` 的筆數；點選嘉惠會看到容量差距；頁尾顯示 `2026-11-11T21:22:47Z`。
- [x] 4.4 [after: 4.3] 實作 Responsive layout：寬度小於 768 px 時，側欄改成預設收合的底部抽屜。驗證：用 DevTools 分別在 1280×800 和 390×844 截圖人工檢查，console 沒有錯誤，手機尺寸下抽屜可以展開和收合。

## 5. 部署與公開

- [x] 5.1 [after: 2.1, 2.2] 依「GitHub Actions 發佈到 Pages」實作 GitHub Pages deployment：新增 `.github/workflows/pages.yml`（push 到 `main` 和 workflow_dispatch 時觸發，依序執行 `make test-web`、`make web`，再 upload 和 deploy `web/`，不跑 Python 資料管線）。README 補上網頁使用方式、`make boundaries`、`make web`、`make test-web` 和網站網址。驗證：用 `actionlint` 或 `gh workflow view` 檢查 workflow 語法（工具不存在時人工對照 design）；README 的指令表包含三個新目標。
- [x] 5.2 [after: 4.4, 5.1] 依「公開前用 git-filter-repo 改寫公司 email」，先詢問使用者 `handoff.md` 要 commit 還是加進 `.gitignore`，並把網頁相關檔案 commit。接著用 `git bundle` 備份，執行 `uvx git-filter-repo`，用 `--mailmap` 和 `--replace-text` 把公司 email 換成 `<id>+SweetCowCow@users.noreply.github.com`；同時替換工作目錄中本 change 的 `.openspec.yaml`，把 repo 的 `git config user.email` 改成 noreply 信箱，並重新加回 `origin`。驗證：`git log --all --format='%ae %ce' | grep -c <公司網域>` 為 0，`git grep <公司網域> $(git rev-list --all)` 沒有結果，`uv run pytest` 和 `make test-web` 仍然通過。
- [x] 5.3 [after: 5.2] **向使用者確認後**，force push `main`；**再次確認後**，執行 `gh repo edit --visibility public --accept-visibility-change-consequences`，把 Pages 來源設成 GitHub Actions，並觸發 workflow，完成 GitHub Pages deployment。最後更新 `handoff.md` 裡的 commit hash。驗證：`gh repo view --json visibility` 為 PUBLIC，`gh run list --workflow pages.yml` 最新一次成功，用 DevTools 開啟 `https://sweetcowcow.github.io/PowerMap/` 時 console 沒有錯誤，且地圖顯示設施和線段。

## 6. 使用者回饋調整（2026-11-13）

> 4.1 已完成的 CARTO 深色圖磚，依「外部圖磚改用 OSM 標準圖磚並以 CSS 調暗」由 6.1 取代；4.3 已完成的能源預設全勾和側欄順序，依「側欄以電力線為主，能源預設不勾」由 6.2 調整。變電所另開 change 4，不在本 change。

- [x] 6.1 依「外部圖磚改用 OSM 標準圖磚並以 CSS 調暗」修改 Base layers：移除 CARTO 圖層，改成「OSM 圖磚（調暗）」（`tile.openstreetmap.org`，CSS filter 只套在這個圖磚圖層上），並把 README 和頁面中提到 CARTO 的地方改成 OSM 圖磚。驗證：用 Chrome DevTools 確認預設狀態下沒有請求 `tile.openstreetmap.org` 和 `cartocdn`；切換到 OSM 圖磚後有載入圖磚、截圖確認畫面偏暗且設施和線段顏色不變、attribution 顯示 © OpenStreetMap contributors；`git grep -i carto -- web README.md` 沒有結果。
- [x] 6.2 依「側欄以電力線為主，能源預設不勾」修改 Energy filter 的預設值和 Legend and footer 的側欄順序：統計電力線在前、電壓篩選 → 只看資料缺口 → 能源篩選，能源預設全部不勾，手機抽屜摘要電力線在前。驗證：DevTools 載入頁面後設施數為 0、線段數為 2,515；按能源的「全選」後設施數為 1,577；側欄 DOM 順序依序為電壓、資料缺口、能源；`make test-web` 通過。
- [x] 6.3 [after: 6.1, 6.2] commit 並 push，確認 GitHub Pages deployment 成功。驗證：`gh run list --workflow pages.yml` 最新一次成功，用 DevTools 開啟 `https://sweetcowcow.github.io/PowerMap/`，初始畫面只有電力線、console 沒有錯誤。

## 7. 底圖與定位工具（2026-11-13 使用者回饋）

- [x] 7.1 依「底圖增加原色 OSM 與國土測繪中心正射影像」擴充 Base layers：layers control 依序為縣市界（離線）、OSM 圖磚（調暗）、OSM 圖磚（原色）、正射影像；README 的資料來源補上國土測繪中心正射影像。驗證：用 DevTools 依序切換三個外部底圖，確認各自有請求 `tile.openstreetmap.org` 或 `wmts.nlsc.gov.tw`，**並截圖人工確認畫面是真正的地圖或影像，而不是錯誤圖片**；原色 OSM 圖磚元素沒有 `osm-dim` class；attribution 顯示國土測繪中心。
- [x] 7.2 依「定位工具放在地圖上方」在 `web/lib.js` 實作 `searchFacilities` 和 `nominatimUrl`。驗證：`web/tests/lib.test.js` 涵蓋 Location tools 規格中設施比對範例表的 3 列，以及 `nominatimUrl` 含 `countrycodes=tw`、`format=jsonv2`、`limit=5`，並對中文與特殊字元做 URL 編碼；`make test-web` 通過。
- [x] 7.3 [after: 7.1, 7.2] 實作 Location tools 的畫面：縣市下拉選單、搜尋框（輸入時列出本地設施；Enter 或「搜尋地名」按鈕才查 Nominatim，兩次查詢至少相隔 1 秒，註明文字會送到 Nominatim）、選取後移動地圖和開啟 Popup，以及失敗和沒有結果時的訊息；桌機和手機版面都可以操作。驗證：用 DevTools 選「臺東縣」後畫面移到臺東；在能源全部不勾的狀態下搜尋「嘉惠」並選取，地圖移過去並開啟 Popup；輸入「台北車站」不按 Enter 時，network 沒有 Nominatim 請求，按 Enter 後才有，選取結果後地圖移過去；搜尋「xyzxyz」顯示找不到；在 1280×800 和手機寬度各截圖檢查，console 沒有錯誤。
- [x] 7.4 [after: 7.3] commit 並 push，確認 GitHub Pages deployment 成功，並在正式網址重做 7.1 的切換底圖檢查和 7.3 的嘉惠搜尋。驗證：`gh run list --workflow pages.yml` 最新一次成功；DevTools 在 `https://sweetcowcow.github.io/PowerMap/` 檢查通過，console 沒有錯誤。

## 8. 統計區塊位置（2026-11-13 使用者回饋）

> 6.2 已完成的「統計在篩選上方」依「統計區塊移到篩選下方並標示會隨篩選變動」由 8.1 調整。

- [x] 8.1 依「統計區塊移到篩選下方並標示會隨篩選變動」修改 Legend and footer 的側欄順序和 Statistics panel：統計移到能源篩選之後、說明與來源之前；分成「目前顯示」（註明會隨篩選變動，數字改變時有顏色提示，reduced motion 時不播放）和「全部資料」（三個固定總數）。驗證：DevTools 確認側欄 DOM 順序為 voltage-filter、gap-toggle、energy-filter、stats、credits；勾選太陽能後設施數改變，且數字元素在 0.6 秒內帶有提示 class；1280×800 截圖確認版面；`make test-web` 通過。
- [x] 8.2 [after: 8.1] commit 並 push，確認 GitHub Pages deployment 成功，並在正式網址確認統計區塊位置。驗證：`gh run list --workflow pages.yml` 最新一次成功；DevTools 在 `https://sweetcowcow.github.io/PowerMap/` 確認側欄順序、console 沒有錯誤。
