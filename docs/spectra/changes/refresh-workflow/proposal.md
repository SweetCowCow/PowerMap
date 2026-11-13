## Why

OSM 快照是 2026-11-11、台電資料是 2026-11-12，之後要定期更新。現在更新要手動刪掉 330 MB 的 OSM 快照、下載台電資料（同一天不能重抓）、跑 `make data`，再自己判斷哪些地方要人工處理。終端只印出幾個數字，看不出這次和上次比變了什麼：OSM 物件被刪除或換 id 後，對照表、位置表、狀態表哪幾列失效，要逐一翻輸出檔才知道。

## What Changes

- 新增 `make refresh`：重新下載 OSM 快照（先下載到暫存檔，成功才取代舊檔）、下載當天的台電資料（當天已下載過就沿用）、執行 `make data`，最後產生變動報告。
- 新增 `powermap/refresh_report.py`：和 git 最新一次 commit 的輸出比較，列出資料來源日期、主要數量的前後變化，以及需要人工處理的項目（尚未審閱的官方電廠、對照表中失效的 OSM id、位置表與狀態表被忽略的列、查證日期超過一年的狀態、新出現的容量差距）。報告印在終端，也存成 `data/interim/refresh_report.md`。
- `powermap/official.py` 的下載指令新增 `--reuse-existing`：當天的目錄已存在時沿用，不報錯。
- README 寫明每月更新步驟和報告中各項目的處理方式。

## Non-Goals

- 不做 GitHub Actions 排程或自動開 PR（之後可以用同一個報告升級）。
- 不自動修改對照表、位置表或狀態表；報告只列出待處理項目。
- 不自動 commit 或部署。

## Capabilities

### New Capabilities

- `data-refresh`: 一個指令更新 OSM 與台電資料並產生和上次 commit 比較的變動報告。

### Modified Capabilities

- `official-power-data`: 下載指令新增 `--reuse-existing`，當天的快照已存在時沿用。

## Impact

- Affected specs: data-refresh（新增）, official-power-data
- Affected code: Makefile, powermap/refresh_report.py（新增）, powermap/official.py, tests/test_refresh_report.py（新增）, tests/test_official.py, README.md
- Affected data: data/interim/refresh_report.md（不 commit）
- 依賴：狀態表的檢查使用 `plant-operating-status` 的 `powermap/official_status.py`，所以本 change 在它之後實作。
