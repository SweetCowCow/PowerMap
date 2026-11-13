## Context

- 2026-11-13 查證：OSM 的 `power=plant`／`generator` 沒有任何 `disused`、`end_date`、`operational_status` 之類的標籤；台電 8934、10858 仍列核一～三的機組和容量，只有龍門寫「封存中」；8931 即時資料只有檢修、歲修、運轉限制等短期備註。
- 官方對照：核一 `w207641187`、核二 `w203381069`、核三 `r7565672`、協和 `r10757938`、興達 `w226576525`、大林 `w204129566` 都以 `same` 連到 OSM（`data/official/crosswalk.csv`）；龍門是 `none`，在 `official_points.geojson` 有估計位置。
- 容量差距報告（`data/processed/official_diff.csv`）中，協和 OSM 2,000／官方 1,000、興達 4,325.95／3,325.95、大林 2,650／2,150，差距來自已除役機組。
- 網頁的設施符號由 `web/lib.js` 的 `facilityStyle` 決定（核能是白色菱形 DivIcon，其他是依能源著色的圓點）；官方估計位置由 `officialPointStyle` 決定。

## Goals / Non-Goals

**Goals:**

- 看地圖就分得出已停止運轉或封存的電廠
- Popup 說明狀態、日期、哪些機組，並附公開來源
- 狀態可追溯、可人工維護，和 OSM 資料分開

**Non-Goals:**

- 不推定沒列在表中的電廠狀態，不顯示「運轉中」
- 不用即時資料的短期狀態
- 不改容量、不改差距報告、不改篩選規則（已停止運轉的電廠仍跟著能源篩選）
- 不處理民營電廠與再生能源場址

## Decisions

### 運轉狀態存成人工確認的 status.csv

新增 `data/official/status.csv`：

| 欄位 | 內容 |
| --- | --- |
| `official_id` | 官方電廠 id |
| `status` | `retired`（已停止運轉）、`mothballed`（封存）、`partially_retired`（部分機組已除役） |
| `since` | 生效日期，`YYYY`、`YYYY-MM` 或 `YYYY-MM-DD`；可空白 |
| `units` | 各機組說明，例如「一號機 2018-12 停機；二號機 2019-07 停機」 |
| `source` | 公開來源網址，必須以 `http://` 或 `https://` 開頭 |
| `checked_at` | 查證日期 `YYYY-MM-DD` |
| `note` | 補充說明 |

第一版收 7 座：核一、核二、核三（`retired`）、龍門（`mothballed`）、協和、興達、大林（`partially_retired`）。日期、機組和來源先整理成草稿給使用者確認，確認後才寫入。沒有列在表中的電廠，網頁不顯示任何狀態。

替代方案是在 `official_plants.json` 加狀態欄位，但官方資料本身沒有這個資訊，混進去會讓人以為是官方提供的，所以不採用。

### 資料管線輸出 official_status.json

新增 `powermap/official_status.py`（CLI：`--official`、`--status`、`--output`）：

- 驗證規則：`official_id` 重複、`status` 不合法、`since` 格式不對、`source` 不是 http(s) 網址、`checked_at` 不是 `YYYY-MM-DD` 時，非 0 退出並印出問題列；`official_id` 不在官方清單時印警告並忽略。
- 輸出 JSON 物件，鍵是 `official_id`（依字母排序），值是 `status`、`since`、`units`、`source`、`checked_at`、`note`；空白欄位輸出 `null`。
- `status.csv` 不存在時輸出 `{}`。

替代方案是直接把狀態寫進 `plants.geojson` 和 `official_points.geojson` 的屬性，但要改兩個資料集的規格和兩個步驟，網頁用 `official_id` 對照一個小檔案就夠了，所以不採用。

### 網頁：灰色符號加 Popup 說明

- `lib.js` 新增 `STATUS_LABELS`（已停止運轉、封存、部分機組已除役）、`statusInactive(status)`（`retired`、`mothballed` 為 true）和 `statusRowsHtml(status)`。
- `facilityStyle(props, status)`：狀態為 inactive 時，圓點填色改成 `#5c6773`（灰色），核能菱形外框也改成同色；其他情況不變。`officialPointStyle(props, status)` 同理改外框顏色。
- `facilityPopupHtml`、`officialPointPopupHtml` 加第二個參數 `status`：有狀態時加上「運轉狀態」（標籤＋日期）、「機組」、「備註」（`note` 有值時；例如核三可申請再運轉、大林五號機仍作緊急備用，這些是給讀者看的補充）和「狀態來源」連結。
- 側欄「其他符號」加一列灰色圓點：「深灰色：已停止運轉或封存的電廠（依公開資訊人工整理，見 Popup 的狀態來源）」。來源不只台電，也包含核安會文件與新聞報導，所以不寫「台電」。
- 篩選、統計不變。

### make web 多複製一個檔案

`WEB_FILES` 加入 `data/processed/official_status.json`，網頁把它列進 `REQUIRED_FILES`。

## Implementation Contract

**行為**

- 確認後的 `status.csv` 有 7 列；`official_status.json` 有 7 個鍵。
- 網頁勾選核能後，核一、核二、核三的菱形是灰色，龍門的官方估計位置虛線圓也是灰色（龍門的 `energy_primary` 是 nuclear）。點開 Popup 有「運轉狀態：已停止運轉」或「封存」、日期和來源連結。
- 協和、興達、大林維持原本顏色，Popup 顯示「部分機組已除役」和機組說明。
- 沒有狀態的電廠 Popup 不出現「運轉狀態」列。

**資料形狀**

- `status.csv`、`official_status.json` 如上。
- `lib.js` 新增 `STATUS_LABELS`、`statusInactive`、`statusRowsHtml`；`facilityStyle`、`facilityPopupHtml`、`officialPointStyle`、`officialPointPopupHtml` 多一個可省略的 `status` 參數。

**失敗模式**

- `status.csv` 格式錯誤：`make data` 非 0 退出並印出問題列。
- `status.csv` 不存在：輸出 `{}`，網頁不顯示狀態。
- 網頁載入不到 `official_status.json`：錯誤橫幅顯示檔名。

**驗收**

- `uv run pytest`、`make test-web` 通過；新增測試涵蓋驗證範例表、缺檔輸出 `{}`、輸出排序與 null、灰色符號、Popup 的狀態列與來源連結 escape、沒有狀態時不出現狀態列。
- 使用者確認過 7 座電廠的狀態內容。
- DevTools 驗證核能灰色、Popup、console；GitHub Pages 部署成功。

**範圍**

- 範圍內：狀態表、`official_status.py`、網頁符號與 Popup、`make web`、README。
- 範圍外：容量與差距報告、篩選、統計、民營電廠。

## Risks / Trade-offs

- [狀態表需要人工維護，可能過時] → 每列有 `checked_at`；README 的更新流程列入檢查（之後的 `refresh-workflow` change 會在變動報告中列出狀態表的查證日期）。
- [灰色可能和「未填能源」的灰色 `#8a94a0` 混淆] → 改用較暗的 `#5c6773`，並在圖例說明；DevTools 截圖確認可分辨。
- [核三 2025 年停機後的除役進度可能變動] → 狀態只寫「已停止運轉」與日期，不寫除役完成。
