## Why

使用者主要想看各地的電力線狀況，但目前地圖上只有線，看不出線路接到哪裡。OSM 快照中有 791 個變電所（2026-11-13 實測，全台含離島，套用本島範圍篩選前），其中 440 個有電壓、650 個有名稱。把變電所放上地圖，就能看出電力線的節點和電壓等級。

## What Changes

- 資料管線的抽取步驟改為也取出 `power=substation`。封閉的 way 和 multipolygon relation 輸出成面，node 輸出成點，並套用既有的本島範圍篩選。`power=tower` 仍然不取。
- 新增 `powermap/substations.py`，輸出 `data/processed/substations.geojson`。每個變電所一個點，屬性包含名稱、營運者、種類（`substation` 標籤）、最高電壓、電壓分級（沿用電力線的 5 級）和缺值旗標。
- `stats.json` 新增變電所總數、缺電壓數，以及依電壓分級的數量。
- 網頁新增變電所圖層：
  - 畫成方形，沿用電力線的電壓配色；缺電壓的畫成灰色空心方形
  - 跟著電壓篩選和「只看資料缺口」一起開關，另外有一個「變電所」開關，預設開啟
  - Popup 顯示名稱、種類、電壓、原始 voltage、營運者和 OSM 連結
  - 搜尋框也能找變電所名稱
  - 統計區塊「目前顯示」加上變電所數
- `make web` 多複製 `substations.geojson`。

## Non-Goals (optional)

（見 design.md 的 Goals / Non-Goals）

## Capabilities

### New Capabilities

- `substation-dataset`：從 OSM 抽取結果產出變電所點資料集，包含電壓解析和分級

### Modified Capabilities

- `osm-power-extraction`：Power feature extraction 改為也輸出 `power=substation`
- `power-data-stats`：新增變電所統計
- `web-map`：新增變電所圖層；資料載入多一個必要檔案
- `web-map-publishing`：`make web` 多複製 `substations.geojson`

## Impact

- 新增檔案：`powermap/substations.py`、`tests/test_substations.py`、`data/processed/substations.geojson`
- 修改：`powermap/osm.py`、`powermap/extract.py`、`powermap/stats.py`、`tests/test_extract.py`、`tests/test_stats.py`、`Makefile`、`README.md`、`web/index.html`、`web/app.js`、`web/lib.js`、`web/style.css`、`web/tests/lib.test.js`
- 資料：重跑 `make data` 後，`power.geojsonseq` 和 `extract_summary.json` 會多出變電所，`stats.json` 會多出變電所欄位；`plants.geojson`、`lines.geojson` 的內容應該不變（會在任務中比對確認）
- 原本規劃的 change 4「官方電廠座標」順延為 change 5
