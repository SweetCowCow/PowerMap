## Context

- `data/processed/unmatched.csv` 目前有 47 座 `no_osm`（2026-11-13）。
- `data/interim/official_plants.json` 的每座電廠都有 `address`。例如「台中市西屯區科園一路1號」（門牌）、「南投縣水里鄉社子段0001-0002地號」（地號）、「桃園市觀音區大潭里、保生里」（村里）、「彰化縣芳苑鄉外海7.2-8.7公里處」（外海描述）。
- `data/official/crosswalk.csv` 的欄位是 `official_id,osm_ids,relation,note`，`osm_ids` 可以用 `;` 列多個，`relation` 有 `same`、`part`、`none`（規格 `official-crosswalk`）。`part` 只設定 `official_id`、`energy_primary`，不合併、不補容量。
- 2026-11-12 的討論時查過：彰工附近有 71 支 OSM 風機，台中港 18 支，大潭／觀園 19 支，麥寮 13 支，香山 6 支；離岸一期附近有一個無名的 OSM plant。
- 風力場址的地址常寫出風機編號分布，例如「彰化縣伸港鄉(#1~#8)、線西鄉(#9~#15)、鹿港鎮(#16~#23)」，可以用來核對風機數量。

## Goals / Non-Goals

**Goals:**

- 風力電廠盡量連到 OSM 現有的風機，不重複畫點
- 其餘官方電廠有可追溯、人工確認過的估計位置
- 地圖上清楚區分「OSM 資料」和「依官方地址估計的位置」

**Non-Goals:**

- 不修改 OSM（不上傳任何資料到 OpenStreetMap）
- 不用付費或需要金鑰的地理編碼服務（例如 TGOS 地址定位、Google）
- 不估計沒有地址或只有縣市層級的位置；查不到就不標，留在 `unmatched.csv`
- 不改 `same`／`part` 的補值規則
- 不處理民營太陽能和風力（沒有逐場官方資料）

## Decisions

### 風力電廠用 part 連到 OSM 風機

每座風力發電站，用台電地址中的村里和風機編號範圍，找出 OSM 上對應範圍內的 `generator`（`generator:source=wind`），數量和官方風機數相符或接近時，用 `part` 連起來，`note` 記錄比對依據，例如「伸港、線西、鹿港沿海 23 支，與官方 #1~#23 相符」。風機數差距大或區域重疊無法分辨（例如大潭和觀園相鄰）時，在 `note` 寫明並請使用者決定。離岸一期如果確認那個無名 OSM plant 就是它，改成 `same`（OSM 缺容量時會補上 109.2 MW）。

人工確認流程沿用 change 2：程式產生候選清單，使用者確認後才寫入 `crosswalk.csv`。替代方案是另外建一張風機對照表，但現有的 `part` 已經可以表達「一座官方電廠對多個 OSM 設施」，所以不採用。

### 估計位置存成人工確認的 locations.csv

新增 `data/official/locations.csv`，欄位如下：

| 欄位 | 內容 |
| --- | --- |
| `official_id` | 官方電廠 id |
| `lat`、`lon` | WGS84，小數 5 位 |
| `precision` | `address`（門牌）、`parcel`（地號）、`village`（村里中心）、`road`（路段或巷弄，查不到門牌時取路段位置）、`site`（從公開資料確認的廠區或設施位置）、`offshore`（外海描述） |
| `method` | `nominatim`、`manual` |
| `source` | 查詢依據，例如 Nominatim 查詢字串，或公開網頁的網址 |
| `checked_at` | 查詢日期 |
| `note` | 補充說明 |

查詢順序是：先用 Nominatim 查門牌地址；查不到或結果明顯不對（不在該鄉鎮）時，改查公開資料（例如機構官網、政府公告）確認廠區位置；只有村里時取村里中心，`precision` 記為 `village`；查到路段或巷弄（長度約 1 公里內）但查不到門牌時，取路段位置，`precision` 記為 `road`，路段太長就不標。所有位置都要給使用者確認後才 commit。

替代方案是在資料管線中即時呼叫 Nominatim，但結果會隨時間改變、需要連網，也違反 Nominatim 不做批次自動查詢的精神，所以不採用。

### 資料管線輸出 official_points.geojson

新增 `powermap/official_points.py`（CLI：`--official`、`--crosswalk`、`--locations`、`--output`）：

- 讀取 `locations.csv`，驗證規則：
  - `official_id` 重複、`precision` 或 `method` 不合法、座標不是數字或超出台灣本島範圍框（`MAIN_BBOX`）時，非 0 退出並印出問題列
  - `official_id` 不在官方清單中時印警告並忽略
  - `official_id` 在對照表中不是 `none` 時印警告並忽略（已經對到 OSM，不需要估計位置）
- 輸出 Point FeatureCollection，屬性依序為：`official_id`、`name`、`county`、`address`、`capacity_mw`、`energy_primary`、`precision`、`method`、`source`、`checked_at`，並依 `official_id` 排序。
- `locations.csv` 不存在時輸出空集合，不報錯，這樣 `make data` 在沒有位置表時仍然可以跑。

`unmatched.csv` 不變：有估計位置的官方電廠，仍然是「OSM 沒有」。

### stats.json 新增 official.located

`official` 物件新增 `located`，等於 `official_points.geojson` 的筆數。其他欄位不變。

### 網頁用空心虛線圓表示官方估計位置

新增一個圖層：
- 符號：半徑 9 px 的空心圓（比電廠點 5 px 和變電所方塊 10 px 大，外圈可以點），外框用官方主要能源的顏色，虛線（`3 3`），中間不填色，和 OSM 的實心點明確區分。放在共用的 `vectors` canvas 上，避免再多一張 canvas 擋住點擊；每次篩選時先加官方點、再加 OSM 設施，讓重疊時 OSM 設施在上層、點中心開 OSM，點外圈開官方點。
- 篩選：跟著能源篩選走，以 `energy_primary` 判斷（`null` 視為 unknown）；另外有一個「台電資料（估計位置）」開關，放在能源區塊最下方，預設開啟。「只看資料缺口」開啟時隱藏，因為這些點都有官方容量。
- Popup：標題是名稱，下面列出「台電資料・位置為依地址估計，不是 OSM 資料」、容量、主要能源、地址、精確程度（門牌／地號／村里／路段／廠區／外海）、查詢日期。
- 搜尋框加上「台電資料」分組。
- 統計區塊「目前顯示」加上這個圖層的數量；「全部資料」中「台電有、OSM 沒標的電廠」後面加上「其中 N 座有估計位置」。

判斷和 Popup 寫在 `lib.js`：`officialPointVisible(props, filters)`、`officialPointPopupHtml(props)`、`PRECISION_LABELS`；`initialFilters()` 新增 `officialPoints: true`。

### make web 多複製一個檔案

`WEB_FILES` 加入 `data/processed/official_points.geojson`，網頁把它列為必要檔案。

### 使用者確認結果（2026-11-13）

- 風力對照：9 座陸域風力電廠用 `part` 連到 OSM 風機（觀園 20、蘆竹 8、香山 6、永興 4、麥寮 23、四湖 14、台中港 18、林口 3、石門 2 支）；彰工只連 8 支標 operator=台電/TPC、ref 28~35 的風機（官方 40 支，其餘和民營風場分不出來）；離岸一期用 `same` 合併無名 OSM 風場範圍和範圍外 7 支 5.2 MW 風機。大潭、台西、台中電廠、恆春維持 `none`。`no_osm` 從 47 座變成 36 座。
- 估計位置：新增 `road`（路段）精確程度，用於查到短巷或 1 公里內路段、但查不到門牌的情況。竹工E/S、龍潭E/S 的官方地址看起來和名稱對調，仍依官方地址放置，`note` 寫明。
- 南投大彎的地址只有地號，但電站名稱中的「大彎」是水里鄉車埕村的聚落，使用者確認以聚落位置估計，`precision` 記為 `village`（例外：用名稱中的聚落定位）。
- 36 座中 30 座有估計位置（廠區 15、門牌 1、村里中心 8、路段 6），6 座不標（只有地號沒有村里，或路段太長）。

## Implementation Contract

**行為**

- 修正對照表並重跑 `make data` 後，`unmatched.csv` 的 `no_osm` 筆數減少（風力電廠連到 OSM 風機），數量以實際結果為準並在任務中記錄；`plants.geojson` 中被連到的風機有 `official_id`。
- `official_points.geojson` 的筆數等於 `locations.csv` 中有效列的數量，`stats.official.located` 相同。
- 網頁勾選太陽能後，看得到官方估計位置的空心虛線圓；點開 Popup 有「位置為依地址估計」字樣；關掉「台電資料（估計位置）」開關時全部隱藏。

**資料形狀**

- `locations.csv` 和 `official_points.geojson` 的欄位如上。
- `lib.js` 新增 `officialPointVisible`、`officialPointPopupHtml`、`PRECISION_LABELS`。

**失敗模式**

- `locations.csv` 格式錯誤：`make data` 非 0 退出並印出問題列。
- `locations.csv` 不存在：輸出空集合，`located` 為 0。
- 網頁載入不到 `official_points.geojson`：錯誤橫幅顯示檔名。

**驗收**

- `uv run pytest`、`make test-web` 全部通過，新增測試涵蓋位置表的各種驗證錯誤、對照表非 `none` 時忽略、輸出欄位和排序、檔案不存在時輸出空集合、`located` 統計、`officialPointVisible` 範例、Popup 的估計字樣和 HTML escape。
- 使用者確認過風力對照和所有估計位置。
- DevTools 驗證圖層顯示、篩選、Popup、搜尋、點擊；GitHub Pages 部署成功。

**範圍**

- 範圍內：對照表的風力修正、位置表、`official_points.py`、統計、網頁圖層、README。
- 範圍外：補值規則、OSM 抽取、變電所、民營電廠。

## Risks / Trade-offs

- [Nominatim 對台灣門牌地址的命中率可能不高] → 查不到時改查公開資料；仍查不到就不標，留在 `unmatched.csv`。
- [估計位置可能被誤認為精確位置] → 用空心虛線符號區分，Popup 明寫「依地址估計」和精確程度。
- [大潭與觀園等相鄰風場的風機分不清] → 在 `note` 寫明，請使用者決定；無法分辨時寧可不連。
- [風機連結後，`official_id` 會出現在 400 多支風機中的一部分上] → 這是 `part` 的既有行為，`energy_primary` 和 OSM 的 `energy` 一致（都是 wind），不影響篩選。

## Migration Plan

本機修改對照表和位置表，經使用者確認後，跑 `make data` 並 commit；網頁完成後 push，由 GitHub Actions 部署。回溯方式是 revert 該 commit。

## Open Questions

- 每座風力電廠的風機連結，以及每個估計位置，都要使用者確認（列在任務中）。
