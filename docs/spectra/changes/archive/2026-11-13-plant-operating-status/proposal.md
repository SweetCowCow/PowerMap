## Why

地圖上看不出哪些電廠已經不發電。核一、核二、核三已停止運轉，龍門封存、未曾商轉，協和、興達、大林有部分機組已除役，但地圖和 Popup 都把它們當成一般電廠，頁尾只能寫「設施出現在圖上，不代表正在運轉」。協和、興達、大林也是容量差距報告裡差距最大的電廠，差距正是除役機組造成的，目前沒有地方說明。

2026-11-13 查證：OSM 的發電設施完全沒有退役相關標籤；台電電廠資料（data.gov.tw 8934、10858）仍列出核一～三的機組和容量，只有龍門寫「封存中」；即時發電資料（8931）只有檢修、歲修等短期狀態。所以運轉狀態只能人工整理，附上公開來源。

## What Changes

- 新增人工確認的運轉狀態表 `data/official/status.csv`：每座官方電廠最多一列，記錄狀態（已停止運轉、封存、部分機組已除役）、生效日期、各機組說明、公開來源網址和查證日期。第一版只收核一、核二、核三、龍門、協和、興達、大林 7 座，內容先整理成草稿給使用者確認再寫入。
- 資料管線新增步驟，驗證狀態表並輸出 `data/processed/official_status.json`（以 `official_id` 為鍵）。
- 網頁讀取 `official_status.json`：有官方對照的設施和官方估計位置，Popup 顯示「運轉狀態」、日期、機組說明和來源連結；已停止運轉或封存的電廠，符號改成灰色。部分機組已除役的維持原本顏色，只在 Popup 說明。
- `make web` 多複製 `official_status.json`；README 說明狀態表的維護方式。

## Non-Goals

- 不推定沒有列在狀態表的電廠的狀態（不顯示「運轉中」）。
- 不使用即時發電資料的檢修、歲修等短期狀態。
- 不逐機組畫在地圖上，也不調整容量數字或容量差距報告的計算。
- 不處理民營電廠和再生能源場址的狀態。
- 不修改 OSM 資料。

## Capabilities

### New Capabilities

- `official-status`: 人工確認的官方電廠運轉狀態表的驗證與輸出。

### Modified Capabilities

- `web-map`: 載入 `official_status.json`，Popup 顯示運轉狀態，已停止運轉或封存的電廠改成灰色符號。
- `web-map-publishing`: `make web` 多複製 `official_status.json`。

## Impact

- Affected specs: official-status（新增）, web-map, web-map-publishing
- Affected code: powermap/official_status.py（新增）, tests/test_official_status.py（新增）, Makefile, web/lib.js, web/app.js, web/index.html, web/style.css, web/tests/lib.test.js, tests/test_make_web.py, README.md
- Affected data: data/official/status.csv（新增）, data/processed/official_status.json（新增）
