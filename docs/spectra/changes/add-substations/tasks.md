## 1. 資料管線

- [x] 1.1 依「抽取時把 substation 當成可組成面的類型」修改 Power feature extraction：`powermap/osm.py` 新增 `AREA_VALUES`，`POWER_VALUES` 加入 `substation`；`powermap/extract.py` 的 area 組裝和封閉 way 判斷改用 `AREA_VALUES`，mixed 能源計數仍只用 `FACILITY_VALUES`。把 `tests/test_extract.py` 的 `test_substation_is_excluded` 改成「變電所面和點都會輸出」，並新增「電塔仍排除」和「金門的變電所計入 kinmen 和 substation」。驗證：`uv run pytest tests/test_extract.py` 通過。
- [x] 1.2 依「變電所資料集沿用設施的點位與電力線的電壓邏輯」實作 Substation dataset output：新增 `powermap/substations.py`（CLI：`--input`、`--output`），輸出欄位和排序依規格。驗證：`tests/test_substations.py` 涵蓋龍潭面轉點範例、缺值範例表 3 列、沒有變電所時輸出空集合；`uv run pytest` 通過。
- [x] 1.3 [after: 1.1, 1.2] 依「stats.json 新增變電所欄位，不改既有欄位」實作 Substation statistics，並在 Makefile 串接：新增變電所步驟（依賴抽取輸出），`stats` 步驟多讀 `substations.geojson`，`make clean` 範圍不變。驗證：`tests/test_stats.py` 新增三個變電所（ehv、missing、missing）和沒有變電所的情境；`uv run pytest` 通過。
- [x] 1.4 [after: 1.3] 執行 `make data` 產生真實資料，記錄本島篩選後的變電所數、缺電壓數和各電壓分級數量，抽查 way 與 relation 重複的情形並記錄數量；確認 `git diff --exit-code data/processed/plants.geojson data/processed/lines.geojson` 沒有差異，且 `stats.json` 既有欄位只有 `built_at` 和 `excluded_outside_main_island`（多計入本島以外的變電所）改變；commit `substations.geojson` 和更新後的 `stats.json`。驗證：上述 diff 指令回傳 0，`substations_by_voltage_class` 總和等於 `substations`。

## 2. 網頁

- [x] 2.1 依「make web 多複製一個檔案」修改 Static site build：`WEB_FILES` 加入 `substations.geojson`。驗證：`make web` 後 `web/data/` 有 6 個檔案；暫時改名 `data/processed/substations.geojson` 時 `make web` 非 0 退出。
- [x] 2.2 依「變電所跟著電壓篩選和資料缺口一起開關」與「Popup、搜尋與統計」，在 `web/lib.js` 實作 `substationVisible`、`substationPopupHtml`、`SUBSTATION_TYPE_LABELS`，`initialFilters()` 新增 `substations: true`。驗證：`web/tests/lib.test.js` 涵蓋 Substation layer 規格的可見性範例 5 列、種類對照範例 7 列、缺值顯示「未命名變電所」和「未填」且不含 null/undefined、HTML escape；`make test-web` 通過。
- [x] 2.3 [after: 1.4, 2.1, 2.2] 依「變電所圖層畫成依電壓著色的方形 DivIcon」實作 Substation layer 和 Map data loading：載入 `substations.geojson`（失敗時橫幅顯示檔名）、方形符號、「變電所」開關與圖例、Popup、搜尋的「變電所」群組、統計區塊的目前顯示數和缺電壓總數。驗證：DevTools 確認預設顯示的變電所數等於 `stats.substations`；取消勾選 ≥345 kV 時對應的線和變電所一起隱藏；關閉「變電所」開關時變電所數為 0、線數不變；開啟只看資料缺口時變電所數等於 `substations_missing_voltage`；搜尋一個變電所名稱並選取會開啟 Popup；暫時改名 `web/data/substations.geojson` 時橫幅顯示檔名；平移縮放沒有明顯卡頓；1280×800 和手機寬度截圖、console 沒有錯誤。
- [x] 2.4 [after: 2.3] README 補上變電所資料集、`stats.json` 新欄位和地圖圖層說明；commit 並 push，確認 GitHub Pages 部署成功。驗證：`gh run list --workflow pages.yml` 最新一次成功；DevTools 在 `https://sweetcowcow.github.io/PowerMap/` 看得到變電所，console 沒有錯誤。

## 3. verify 與 review 回饋（2026-11-13）

- [x] 3.1 依「電力線與設施共用一張 canvas，變電所圖層放在最上層」修正 Substation layer 的點擊：電力線和設施共用 `vectors` pane 的 canvas renderer，變電所 pane 改到 z 430。驗證：DevTools 在能源全選、全不選、開關電壓分級之後，分別點擊同一個變電所、一段電力線、一座電廠，三者都會開啟 Popup（設施隱藏時除外）。
- [x] 3.2 依「電壓勾選框同時顯示線段數和變電所數」修改電壓勾選框的數字為「N 段・M 座」；並把 Map data loading 中「找出載入失敗的必要檔案」抽成 `lib.js` 的 `failedFiles(names, settled)`。驗證：`web/tests/lib.test.js` 新增 `substations.geojson` 回 404 時回傳 `["substations.geojson"]`、全部成功時回傳空陣列；DevTools 確認 ≥345 kV 那列顯示「264 段・31 座」；`make test-web` 通過。
- [x] 3.3 `powermap/stats.py` 的 `--substations` 改為必填，`compute_stats` 的 `substations` 參數也改為必填；`tests/test_stats.py` 的 CLI 測試補上「缺電壓變電所」那一行的斷言。驗證：`uv run pytest` 通過；`make -n data` 顯示 stats 指令有帶 `--substations`。
- [ ] 3.4 依「部署時為網頁檔案加上版本號」修改 `.github/workflows/pages.yml`：`make web` 後，替 `index.html` 的 `app.js`、`style.css` 和 `app.js` 的 `./lib.js` 加上 `?v=<commit 前 7 碼>`。驗證：actionlint 通過；部署後，正式網址的 `index.html` 含 `app.js?v=`，`app.js` 含 `lib.js?v=`。
- [ ] 3.5 [after: 3.1, 3.2, 3.3, 3.4] commit、push，確認部署成功，並在正式網址重做 3.1 的點擊檢查。驗證：`gh run list --workflow pages.yml` 最新一次成功；DevTools 檢查通過，console 沒有錯誤。

> 不另寫自動測試的項目：變電所搜尋群組的結果呈現（`app.js` 的畫面組裝，改壞了搜尋時就看得到，已在 2.3 和 3.5 用 DevTools 檢查）；`make web` 缺檔時失敗（Makefile 被讀取時就會改寫參數戳記與資料檔時間，不適合在 pytest 中執行，已在 2.1 手動驗證）。
