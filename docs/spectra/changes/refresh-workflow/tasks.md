## 1. 下載

- [x] 1.1 依「下載指令新增 --reuse-existing」修改 Official snapshot download：`python -m powermap.official download --reuse-existing` 在當天目錄已存在時沿用並以 0 結束。驗證：`tests/test_official.py` 涵蓋有參數時沿用（檔案不變、沒有下載）、沒有參數時仍非 0 退出；`uv run pytest` 通過。

## 2. 變動報告

- [x] 2.1 依「變動報告和 git HEAD 比較」實作 Change report：新增 `powermap/refresh_report.py`（`build_report` 回傳 Markdown，CLI 讀 git ref 和目前輸出並寫入 `--output`）。驗證：`tests/test_refresh_report.py` 涵蓋規格範例表 4 列、base 缺 `official_diff.csv` 時全部列為新差距、位置表與狀態表被忽略的列、git ref 不存在時非 0 退出；`uv run pytest` 通過。

## 3. 指令與文件

- [x] 3.1 [after: 1.1, 2.1] 依「make refresh 的步驟」實作 Refresh command：Makefile 新增 `refresh`（OSM 先下載到 `.new` 再取代、台電資料 `--reuse-existing`、`make data`、產生報告）。驗證：用不存在的 `SNAPSHOT_URL` 執行 `make refresh` 時非 0 退出且 `data/raw/taiwan-latest.osm.pbf` 的修改時間不變。
- [ ] 3.2 [after: 3.1] README 寫明每月更新步驟與報告各項目的處理方式；實際執行一次 `make refresh`，把報告摘要給使用者看，由使用者決定是否 commit 新資料。驗證：`data/interim/refresh_report.md` 存在，報告中 `unreviewed` 的筆數等於 `unmatched.csv` 中的筆數；`uv run pytest` 通過。
