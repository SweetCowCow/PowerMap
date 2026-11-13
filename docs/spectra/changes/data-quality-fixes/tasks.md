## 1. 變電所去重

- [x] 1.1 依「只去掉被包住、而且沒有名稱或同名的變電所」和「去重紀錄寫成獨立檔案」實作 Contained substation removal，並更新 Substation dataset output（只有被包住的變電所會被去掉）：`powermap/substations.py` 在 EPSG:3826 判斷包含關係，去掉被包住且沒有名稱或同名的變電所，CLI 新增必填 `--dedup-log` 輸出 `substation_dedup_log.csv`；Makefile 的變電所步驟加上這個輸出。驗證：`tests/test_substations.py` 涵蓋規格範例表 5 列（沒有名稱被包住去掉、同名去掉、名稱不同保留、只相鄰保留、89% 保留）、紀錄欄位與排序、沒有去重時只有標題列；既有變電所測試仍通過；`uv run pytest` 通過。

## 2. 大觀改成 part

- [x] 2.1 依「大觀改成 part」修改 `data/official/crosswalk.csv` 大觀那一列（relation 改 `part`，`note` 寫明一廠、二廠各自保留 OSM 容量）。驗證：`git diff data/official/crosswalk.csv` 只改這一列。

## 3. 重跑資料與文件

- [x] 3.1 [after: 1.1, 2.1] 執行 `make data`，確認 `substations.geojson` 不含 `w942837398`、`w942837397`、`w659199805`、`w807986863` 而仍含 `w323405078`、`w323413321`、`r17867618`，`substation_dedup_log.csv` 有這 4 列，`stats.json` 的 `substations` 等於輸出筆數（預期 784）；`plants.geojson` 的 `w1105678337` 1,000 MW、`w976767036` 110 MW、`w515759414` 容量 null，三筆 `official_id` 都是 `tp-plant:大觀發電廠`。README 補上變電所去重規則和 `substation_dedup_log.csv`。`make web` 後用 DevTools 確認網頁變電所數字為新的總數、console 沒有錯誤；commit、push，確認 GitHub Pages 部署成功。
