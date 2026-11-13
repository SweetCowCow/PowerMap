## 1. 狀態表

- [x] 1.1 依「運轉狀態存成人工確認的 status.csv」，為核一、核二、核三、龍門、協和、興達、大林查公開資料（台電、核安會等官方網頁或新聞稿），整理每座的 `status`、`since`、`units`、`source`、`note`，存成暫存區的草稿表給使用者確認，不直接寫入 repo。驗證：草稿表 7 列都有 http(s) 來源網址和機組說明；查不到可靠來源的欄位寫明「待確認」。
- [x] 1.2 [after: 1.1] 使用者確認後，寫入 `data/official/status.csv` 並 commit。驗證：筆數和使用者確認的一致，每列都有 `source` 和 `checked_at`。

## 2. 資料管線

- [x] 2.1 依「資料管線輸出 official_status.json」實作 Official status table validation 和 Official status output：新增 `powermap/official_status.py`，Makefile 新增步驟並納入 `make data`。驗證：`tests/test_official_status.py` 涵蓋驗證範例表 6 列、檔案不存在時輸出 `{}`、核一的輸出範例（含 `note` 為 null）、鍵排序；`uv run pytest` 通過。
- [x] 2.2 [after: 1.2, 2.1] 執行 `make data`，確認 `official_status.json` 有 7 個鍵、沒有警告；commit 資料。驗證：鍵數等於 `status.csv` 的有效列數。

## 3. 網頁

- [x] 3.1 依「make web 多複製一個檔案」修改 Static site build，並把 `official_status.json` 加入網頁的 `REQUIRED_FILES`（Map data loading）。驗證：`make web` 後 `web/data/` 有 8 個檔案；`tests/test_make_web.py` 改成 8 個檔案並涵蓋缺 `official_status.json` 時失敗；`failedFiles` 測試涵蓋 `official_status.json`；`uv run pytest`、`make test-web` 通過。
- [x] 3.2 依「網頁：灰色符號加 Popup 說明」在 `web/lib.js` 實作 Operating status display 的判斷與 HTML：`STATUS_LABELS`、`statusInactive`、`statusRowsHtml`，`facilityStyle`、`officialPointStyle`、`facilityPopupHtml`、`officialPointPopupHtml` 接受 `status`。驗證：`web/tests/lib.test.js` 涵蓋規格範例表 4 列（灰色菱形、灰色虛線圓、部分除役維持顏色、沒有狀態不出現狀態列）、來源連結與文字 escape；`make test-web` 通過。
- [x] 3.3 [after: 2.2, 3.1, 3.2] 在 `web/app.js` 把狀態傳給符號與 Popup（含搜尋開啟的 Popup），`web/index.html` 圖例加上灰色說明。驗證：DevTools 勾選核能後核一～三是灰色菱形、龍門虛線圓是灰色，點開 Popup 有「已停止運轉」與來源連結；協和 Popup 有「部分機組已除役」；台中發電廠沒有狀態列；1280×800 與手機寬度截圖、console 沒有錯誤。
- [ ] 3.4 [after: 3.3] README 補上 `status.csv` 的維護方式、`official_status.json` 和灰色符號說明；commit、push，確認 GitHub Pages 部署成功。驗證：`gh run list --workflow pages.yml` 最新一次成功；DevTools 在正式網址看到灰色核能符號，console 沒有錯誤。
