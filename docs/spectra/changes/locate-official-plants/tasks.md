## 1. 風力電廠連到 OSM 風機

- [x] 1.1 依「風力電廠用 part 連到 OSM 風機」，為 `unmatched.csv` 中每座風力發電站（以及離岸一期）產生候選清單：依台電地址的村里和風機編號，找出範圍內的 OSM wind generator（和可能的 OSM plant），列出數量和官方風機數。清單存到暫存區給使用者看，不直接改對照表。驗證：清單涵蓋所有 `energy_primary` 為 wind 且 relation 為 `none` 的官方電廠，每座都有候選的 OSM id、數量和比對依據。
- [x] 1.2 [after: 1.1] 使用者確認後，修改 `data/official/crosswalk.csv`：確認的風力電廠改成 `part`（離岸一期如果確認，改成 `same`），`note` 記錄比對依據；無法分辨的維持 `none` 並寫明原因。執行 `make data`，記錄 `no_osm` 從 47 變成多少。驗證：`make data` 成功，終端顯示 ignored crosswalk ids 為 0；`git diff data/official/crosswalk.csv` 只改到風力的列。

## 2. 估計位置

- [x] 2.1 依「估計位置存成人工確認的 locations.csv」，為仍是 `none` 的官方電廠查座標：先用 Nominatim 查地址（每秒最多 1 次），查不到或不在該鄉鎮時改查公開資料，只有村里時取村里中心。結果存成暫存區的草稿表，附上每筆的查詢依據和地圖連結，給使用者確認。驗證：每座都有座標或「查不到」的說明；草稿表的欄位和 design 一致。
- [x] 2.2 [after: 2.1] 使用者確認後，寫入 `data/official/locations.csv` 並 commit。驗證：`locations.csv` 的筆數和使用者確認的一致；每列都有 `source` 和 `checked_at`。
- [x] 2.3 依「資料管線輸出 official_points.geojson」實作 Official location table validation 和 Official point output：新增 `powermap/official_points.py`，Makefile 新增步驟（讀官方清單、對照表、位置表）。驗證：`tests/test_official_points.py` 涵蓋驗證範例表的 6 列、檔案不存在時輸出空集合、中科 E/S 的輸出範例（含仍在 `unmatched.csv`）、欄位順序和排序；`uv run pytest` 通過。
- [x] 2.4 [after: 2.3] 依「stats.json 新增 official.located」實作 Located official plant count。驗證：`tests/test_stats.py` 新增 30 筆時 `located` 為 30 的情境，既有統計測試仍通過；`uv run pytest` 通過。
- [ ] 2.5 [after: 1.2, 2.2, 2.4] 執行 `make data`，確認 `official_points.geojson` 的筆數等於 `stats.official.located`，也等於 `locations.csv` 的有效列數；commit 資料。驗證：上述三個數字相同，`make data` 沒有警告。

## 3. 網頁

- [ ] 3.1 依「make web 多複製一個檔案」修改 Static site build，並把 `official_points.geojson` 加入網頁的必要檔案（Map data loading）。驗證：`make web` 後 `web/data/` 有 7 個檔案；`failedFiles` 測試涵蓋 `official_points.geojson` 失敗；`make test-web` 通過。
- [ ] 3.2 依「網頁用空心虛線圓表示官方估計位置」在 `web/lib.js` 實作 `officialPointVisible`、`officialPointPopupHtml`、`PRECISION_LABELS`，`initialFilters()` 新增 `officialPoints: true`。驗證：測試涵蓋 Official estimated location layer 的可見性範例 5 列、Popup 含「依地址估計」「不是 OSM 資料」和精確程度標籤、缺值不出現 null/undefined、HTML escape；`make test-web` 通過。
- [ ] 3.3 [after: 2.5, 3.1, 3.2] 實作 Official estimated location layer 的畫面：空心虛線圓（共用 `vectors` canvas）、「台電資料（估計位置）」開關、Popup、搜尋的「台電資料」分組、統計區塊的目前顯示數和「其中 N 座有估計位置」。驗證：DevTools 勾選太陽能後看得到官方點，數量等於 energy_primary 為 solar 的官方點數；關掉開關時為 0；開啟只看資料缺口時為 0；點官方點、變電所、電力線、電廠都會開 Popup；搜尋一個官方電廠名稱並選取會開 Popup；1280×800 和手機寬度截圖、console 沒有錯誤。
- [ ] 3.4 [after: 3.3] README 補上位置表的維護方式、`official_points.geojson` 和地圖圖層說明；commit、push，確認 GitHub Pages 部署成功。驗證：`gh run list --workflow pages.yml` 最新一次成功；DevTools 在正式網址看得到官方估計位置圖層，console 沒有錯誤。
