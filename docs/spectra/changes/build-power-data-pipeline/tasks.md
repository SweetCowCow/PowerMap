## 1. 專案骨架與環境

- [x] 1.1 依「以 uv 管理 Python 3.11 與相依套件」與「專案根目錄即 repo 根目錄」建立可執行的專案環境：uv 安裝於 `~/.local/bin`，`pyproject.toml` 宣告 Python ≥ 3.11 及 osmium、geopandas、shapely、pandas、pyogrio、pytest，產生 `uv.lock`，並在 repo 根目錄建立 `powermap/`、`scripts/`、`tests/`、`data/raw/`、`data/interim/`、`data/processed/`。驗證：`uv run python --version` 顯示 3.11 以上，且 `uv run python -c "import osmium, geopandas, shapely, pyogrio"` 成功。
- [x] 1.2 [after: 1.1] 依「原始與中間資料不進 git，processed 輸出進 git」與「程式邏輯放在 powermap 套件，Makefile 串接步驟」：`.gitignore` 排除 `data/raw/`、`data/interim/`，Makefile 提供 `data`、`extract`、`test`、`clean` 四個 target，`clean` 不刪 `data/raw/`。驗證：`git check-ignore data/raw/a data/interim/a` 兩者皆命中、`git check-ignore data/processed/a` 不命中，`make -n data` 列出的步驟順序為下載、抽取、設施、電力線、統計。

## 2. 下載與抽取

- [x] 2.1 [after: 1.2] 實作 Snapshot download：`scripts/download.sh` 先下載到暫存檔再搬到 `data/raw/taiwan-latest.osm.pbf`，檔案已存在時跳過，失敗時以非零結束碼退出且不留下目標檔。驗證：首次 `make extract` 下載成功；再跑一次終端沒有下載輸出；以環境變數把下載網址改成無效網址時，指令非零退出且目標路徑沒有檔案。
- [x] 2.2 [after: 1.1] 依「以 pyosmium 取代 osmium-tool CLI 進行過濾與匯出」在 `powermap.extract` 實作 Power feature extraction 與 Snapshot timestamp recording：只輸出五種 `power` 值、plant／generator 的封閉 way 與 multipolygon 為面、line／minor_line／cable 為線、area id 換回原始 way／relation id、每筆帶全部標籤與 `osm_type`，快照時間取自 pbf header，缺少時記 `null` 並警告。驗證：`tests/test_extract.py` 以 `tests/fixtures/` 內的小型 OSM 檔測試「封閉 plant way 為 Polygon 且 id 正確」、「封閉 cable way 為 LineString」、「substation 不輸出」、「header 有／無快照時間」四個情境，`uv run pytest tests/test_extract.py` 通過。
- [x] 2.3 [after: 2.2, 3.1] 依「以範圍框限定台灣本島，跨界圖徵整條保留」實作 Main island scope filter（`--main-bbox` 預設經度 119.9–122.2、緯度 21.8–25.4，排除圖徵歸入 `kinmen`／`matsu`／`penghu`／`other`，保留圖徵不裁切），並實作 Extraction summary：終端輸出與 `data/interim/extract_summary.json` 一致，含快照時間、保留圖徵的 `power` 值 × 幾何類型數量、無幾何 relation 數、多能源（`mixed`）設施筆數、各區排除數量與 `other` 類排除的 OSM id 清單、無效幾何跳過數。驗證：`tests/test_extract.py` 把 spec 範圍判定範例表每一列寫成參數化測試（含台澎海纜整條保留），並測試「3 筆 `coal;gas` 加 1 筆 `solar` → 多能源 3 筆」與「金門 40 筆、東沙 2 筆 → `kinmen` 40、`other` 2 且列出 2 個 id」，全數通過。
- [x] 2.4 [after: 2.1, 2.3] 人工檢查點：執行 `make extract`，把 Extraction summary 的數字（各類數量、多能源筆數、金門／馬祖／澎湖／其他的排除數量、`other` 類排除清單）、快照時間與 `ls -lh data/raw/` 量到的快照大小整理成表格回報使用者，並停下等待確認；使用者確認前不開始第 4、5 組任務。驗證：使用者在對話中明確確認抽取結果（或提出要調整的地方並已處理）。
- [x] 2.5 [after: 2.4] 依 2.4 檢查點的決定修正 Main island scope filter：`--main-bbox` 預設改為經度 119.3–122.2、緯度 21.8–25.4，另外排除整個落在澎湖範圍框內的圖徵，排除區域依 `penghu`→`kinmen`→`matsu`→`other` 順序判定（取代 2.3 的原預設值）。驗證：`tests/test_extract.py` 的範圍判定參數化測試涵蓋 spec 範例表全部列（含彰化外海風場保留、福建外海風場歸入 `other`、台澎海纜保留），`make extract` 在真實快照上保留 4,841 筆、`other` 排除 122 筆。

## 3. 解析器

- [x] 3.1 [after: 1.1] 在 `powermap.parsers` 實作四個純函式，滿足各規則：`classify_energy` 回傳 `(energy, energy_sources)`，依「多能源設施標為 mixed 並保留全部來源」實作 Energy classification；`parse_capacity_mw` 實作 Capacity parsing（純數字視為 MW）；`parse_voltage_max_kv` 實作 Voltage parsing；`classify_voltage` 實作 Voltage classification。驗證：`tests/test_parsers.py` 把 spec 中能源、容量、電壓、分級四張範例表的每一列都寫成參數化測試，`uv run pytest tests/test_parsers.py` 全數通過。

## 4. 設施資料集

- [x] 4.1 [after: 2.5, 3.1] 在 `powermap.facilities` 實作 Facility point geometry 與基本屬性：plant／generator 以 `representative_point()` 轉點並記錄 `geom_src`，填入 `energy`、`energy_sources`、`source_raw`、`capacity_mw`、`capacity_raw`、`missing_capacity`、`missing_energy`、`name`（`name` → `name:zh` → `null`）、`operator`、`osm_id`、`osm_url`，並依「屬性值附帶資料來源欄位」實作 Facility value provenance（`capacity_source`、`energy_data_source`）。驗證：`tests/test_facilities.py` 測試「凹多邊形 plant 的輸出點落在多邊形內且 `geom_src` 為 Polygon」、「way 123456 得到 `w123456` 與對應 `osm_url`」、「有容量無來源標籤的 plant → `capacity_source` 為 `osm`、`energy_data_source` 為 null」，`uv run pytest tests/test_facilities.py` 通過。
- [x] 4.2 [after: 4.1] 實作 Generators inside plants are aggregated 與 Standalone rooftop and small solar exclusion，依「去重採保守規則且參數可調」提供 `--rooftop-threshold-mw`（預設 1），歸併寫入 `dedup_log.csv`（action `generator_in_plant`），排除數量供統計使用。驗證：`tests/test_facilities.py` 測試「12 支 generator 在同一 plant 面內 → `n_generators` 為 12 且 log 有 12 列」、「點落在兩個重疊 plant 時歸給面積較小者」，以及 spec 屋頂規則範例表的每一列。
- [x] 4.3 [after: 4.2] 實作 Same-name node and area duplicates are merged（依「距離與簡化在 EPSG:3826 計算」量距離，`--dedup-distance-m` 預設 500）與 Facility dataset output：寫出 `data/processed/plants.geojson` 與含標頭 `action,kept_osm_id,dropped_osm_id,reason,distance_m` 的 `dedup_log.csv`，屬性欄位集合與 spec 完全一致（含 `energy_sources`、`capacity_source`、`energy_data_source`），缺值為 `null`、`energy_sources` 缺值為空陣列。驗證：`tests/test_facilities.py` 測試「同名相距 120 m 只留 way」、「同名相距 800 m 兩筆都留」、「輸出屬性 key 集合等於 spec 清單且缺值欄位沒有 0 或空字串」。

## 5. 電力線資料集

- [x] 5.1 [after: 2.5, 3.1] 在 `powermap.lines` 實作 One feature per OSM way without merging、Line geometry simplification（EPSG:3826、10 m、保留拓撲、座標四捨五入到 5 位、無效結果跳過並計數警告）、Line value provenance（`voltage_source`）與 Line dataset output（寫出 `data/processed/lines.geojson`，屬性欄位與 spec 一致）。驗證：`tests/test_lines.py` 測試「共用端點的兩條 way 輸出兩筆」、「輸出座標小數位數不超過 5」、「無 voltage 的 minor_line 各欄位為 null、`voltage_class` 為 missing、`voltage_source` 為 null」、「`voltage=161000` 的線 `voltage_source` 為 osm」、「`location=underwater` 的 cable 保留 location」，`uv run pytest tests/test_lines.py` 通過。

## 6. 統計與整合

- [x] 6.1 [after: 4.3, 5.1] 在 `powermap.stats` 實作 Statistics file 與 Terminal summary：由輸出檔計算 `stats.json` 全部欄位，十種 `by_energy`、八種 `by_energy_source`、五種電壓分級即使為 0 也列出，`excluded_outside_main_island` 取自抽取摘要，最後印出統計摘要。驗證：`tests/test_stats.py` 測試「沒有地熱設施時 `by_energy.geothermal` 為 0」、「`by_energy` 總和等於 `facilities`、`by_voltage_class` 總和等於 `lines`」、「一筆 `["coal","gas"]` 加一筆 `["gas"]` → `by_energy.mixed` 1、`by_energy_source.gas` 2」並通過。
- [x] 6.2 [after: 2.1, 6.1] 串接 `make data` 端到端，並在 `README.md` 寫入資料管線說明（安裝 uv、`make data`／`make test`／`make clean`、資料來源與「© OpenStreetMap contributors」ODbL 標示、缺值保持 null 的原則、`mixed` 與 `energy_sources` 的意義、目前只含台灣本島與鄰近島嶼、資料只來自 OSM 且官方交叉驗證為後續工作、改用 pyosmium 的原因）。驗證：刪除 `data/interim/` 與 `data/processed/` 後執行 `make data` 成功，產出 `plants.geojson`、`lines.geojson`、`stats.json`、`dedup_log.csv` 四個檔且終端最後是統計摘要；`make test` 全數通過；README 內容經檢查包含上述各項。

## 7. 驗收

- [x] 7.1 [after: 6.2] 依需求文件第 8 節做資料面驗收，結果整理成表格回報使用者：設施數與線段數對照原作參考值（約 700、約 2,100，原作含離島，比較時註明；差距超過 30% 時列出可能原因與案例）、抽查大潭、通霄、興達、台中、萬大、核一、核二、核三、和平、麥寮 10 座電廠的位置、`energy` 與 `energy_sources`、以腳本確認所有缺值欄位為 `null`（無 0 或空字串）、以腳本確認輸出中沒有完全落在金門／馬祖／澎湖範圍框內的圖徵、`lines.geojson` 未壓縮小於 5 MB，並列出所有 `mixed` 設施、純數字容量案例與離岸風場案例。驗證：報告已交付，且使用者對去重門檻、離岸風場是否聚合做出決定。
- [x] 7.2 [after: 7.1] 依使用者在 7.1 的決定調整 `--rooftop-threshold-mw`／`--dedup-distance-m` 預設值（若有變更），重跑 `make data`，並以 git commit 保存 `data/processed/` 輸出。驗證：`git ls-files data/processed` 列出四個輸出檔，`stats.json` 的 `built_at` 為本次重跑時間。

## 變更紀錄

2026-11-12 依使用者決定更新（無已完成任務受影響）：多能源由「取第一個來源」改為 `mixed`＋`energy_sources`（影響 2.3、3.1、4.1、4.3、6.1、7.1）；新增資料來源欄位（4.1、4.3、5.1）；新增本島範圍篩選並排除金門、馬祖、澎湖（2.3、2.4、6.1、6.2、7.1），原「確認金門馬祖澎湖有資料」的驗收改為「確認已排除」。

2026-11-12 2.4 檢查點：彰化外海離岸風場位於原本島範圍框西邊界外而被誤排除；已完成的 2.3 保留原紀錄，新增 2.5 修正範圍規則，4.1、5.1 改為接在 2.5 之後。
