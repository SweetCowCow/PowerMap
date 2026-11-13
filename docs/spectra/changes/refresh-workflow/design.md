## Context

- `scripts/download.sh` 在 `data/raw/taiwan-latest.osm.pbf` 已存在時直接跳過，要重抓得先手動刪檔（約 330 MB，2026-11-12 下載）。
- `python -m powermap.official download` 在當天的 `data/official/raw/<YYYY-MM-DD>/` 已存在時報錯（規格 `official-power-data`）；`make data` 預設讀最新的日期目錄。
- `make data` 的各步驟已經把審閱相關的結果寫在輸出中：`unmatched.csv` 的 `reason`（`unreviewed`、`osm_missing`）、`data/interim/enrich_meta.json` 的 `ignored_crosswalk_ids` 和 `warnings`、`official_diff.csv`、`stats.json`。位置表被忽略的列只印在終端（`powermap/official_points.py` 的 `load_locations` 回傳 `warnings`）。
- `data/processed/` 都有 commit，所以「上次」可以用 git 最新 commit 的版本。
- 狀態表 `data/official/status.csv` 和 `powermap/official_status.py` 由 `plant-operating-status` 新增；本 change 在它之後實作。

## Goals / Non-Goals

**Goals:**

- 一個指令完成下載與重建
- 一份報告說明這次和上次差在哪、哪些需要人工處理

**Non-Goals:**

- 不做排程、不自動開 PR、不自動 commit 或部署
- 不自動修改人工維護的表
- 報告不比較每一筆設施的屬性變化（只比數量和待處理清單）

## Decisions

### make refresh 的步驟

```
make refresh
  1. scripts/download.sh data/raw/taiwan-latest.osm.pbf.new → 成功後 mv 取代舊檔
  2. python -m powermap.official download --reuse-existing
  3. $(MAKE) data
  4. python -m powermap.refresh_report --base-ref HEAD --output data/interim/refresh_report.md
```

OSM 先下載到 `.new`，失敗時舊快照還在，`make data` 仍可用。任何一步失敗就停止（非 0 退出）。

### 下載指令新增 --reuse-existing

`download --reuse-existing`：當天目錄已存在時印出「沿用 <目錄>」並成功結束；沒有這個參數時維持原本的拒絕覆寫行為。`make official-download` 不變。

### 變動報告和 git HEAD 比較

`powermap/refresh_report.py`（CLI：`--base-ref`，預設 `HEAD`；`--output`）用 `git show <ref>:<path>` 讀上次 commit 的 `data/processed/stats.json`、`unmatched.csv`、`official_diff.csv`；檔案在該 commit 不存在時視為空。報告是 Markdown，內容依序為：

1. **資料來源**：OSM 快照時間、官方資料目錄，前後對照。
2. **數量變化**：設施、電力線、變電所、對到 OSM 的官方電廠、OSM 沒有的官方電廠、有估計位置的官方電廠、缺容量設施、缺電壓線段，各列「上次、這次、差」。
3. **待處理**（每項列出 id 和處理方式）：
   - `unmatched.csv` 中 `unreviewed` 的官方電廠 → `make crosswalk-candidates` 後編輯 `crosswalk.csv`
   - `osm_missing` 的官方電廠（對照表的 OSM id 已失效）
   - `enrich_meta.json` 的 `warnings`（被忽略的對照表 id）
   - 位置表被忽略的列（用 `load_locations` 重新檢查）
   - 狀態表被忽略的列，以及 `checked_at` 距今超過 365 天的列
   - `official_diff.csv` 中上次沒有的新容量差距
4. 最後一行：`待處理 N 項`。

報告同時印在終端並寫入 `--output`；即使有待處理項目也以 0 結束（只有讀檔或 git 失敗才非 0）。替代方案是在 `make refresh` 前先複製一份舊輸出，但 git 已經保存了上次的版本，不需要另存。

### 報告存在 data/interim/，不 commit

`data/interim/` 已在 `.gitignore`；報告是給人看的工作檔，處理完成後的結果會反映在 commit 的資料中。

## Implementation Contract

**行為**

- `make refresh` 依序下載、重建、產生報告；OSM 下載失敗時舊快照不被刪除。
- 當天已下載過台電資料時，`make refresh` 沿用而不失敗。
- 報告的待處理項目和輸出檔一致（例如 `unreviewed` 筆數等於 `unmatched.csv` 中的筆數）。

**資料形狀**

- `refresh_report.md` 依上述 4 段排列；`build_report(base, current, today)` 回傳 Markdown 字串，方便測試。

**失敗模式**

- `--base-ref` 不存在或不在 git repo 中：非 0 退出並印出原因。
- 某個輸出檔在 base 不存在：視為空，數量變化顯示上次為 0。

**驗收**

- `tests/test_refresh_report.py` 涵蓋：數量變化的差值、各類待處理項目各至少一例、沒有待處理時顯示 `待處理 0 項`、base 缺檔視為空、狀態表超過 365 天的判斷（以固定的 today 測試）。
- `tests/test_official.py` 涵蓋 `--reuse-existing` 沿用既有目錄、沒有參數時仍拒絕。
- `uv run pytest` 通過；在本機實際執行一次 `make refresh`，報告內容和輸出檔一致。

**範圍**

- 範圍內：Makefile、`refresh_report.py`、`official.py` 下載參數、README。
- 範圍外：排程、自動 PR、自動修改人工表。

## Risks / Trade-offs

- [實際執行 make refresh 會下載新資料，可能帶來大量變動] → 實作最後一步會實際跑一次，變動內容先給使用者看，再決定是否 commit 新資料。
- [git show 依賴工作目錄是 git repo] → 失敗時報錯說明，不影響 `make data`。
