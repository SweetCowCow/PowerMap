## Why

2026-11-13 查證 Roadmap 上的兩個資料品質疑點，結果和原本記錄的不同：

- 變電所：原本記「11 組 relation 和 way 可能重複」，實際比對範圍後，只有 1 組相鄰而且不重疊、名稱也不同，不是重複。真正重複的是另一種情況：一個變電所的範圍完全包在另一個變電所裡，而且沒有名稱或和外面同名（目前 4 處），地圖上會疊兩個方塊。
- 合併容量：用 `same` 合併多筆 OSM 的電廠有 5 座，只有大觀算錯（輸出 1,000 MW，官方 1,110 MW）。改成「合併時加總」會讓大潭（同一座畫了兩個範圍，變成 9,968.4 MW）和離岸一期（只有 7 支風機有容量，變成 36.4 MW）變錯，所以問題在大觀的對照方式，不在規則。

## What Changes

- 變電所資料集新增一條窄的去重規則：一個變電所的範圍有 90% 以上落在另一個較大的變電所範圍內時，兩者只有一個有名稱就去掉沒名稱的那個，同名就去掉裡面那個，並寫進新的 `data/processed/substation_dedup_log.csv`。名稱不同的（例如同盟變電所和台電電力修護處南部分處）保留。
- `data/official/crosswalk.csv` 的大觀發電廠由 `same` 改成 `part`：二廠（1,000 MW）、一廠（110 MW）和沒有容量的整體範圍各自保留，不合併、不補容量。`same` 的合併規則不變。
- README 更新變電所去重說明和新的紀錄檔。

## Non-Goals

- 不改 `same` 合併時的容量規則（不加總）。
- 不處理距離近但範圍不重疊的變電所，也不處理通用名稱（「變電所」「開關場」「配電室」）相同但位置不同的變電所，它們是不同設施。
- 不處理只有點（node）的變電所的包含關係。
- 不修改 OSM 資料。

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `substation-dataset`：輸出時去掉「被另一個變電所範圍包住、而且沒有名稱或同名」的變電所，並輸出去重紀錄。

## Impact

- Affected specs: substation-dataset
- Affected code: powermap/substations.py, tests/test_substations.py, Makefile, README.md
- Affected data: data/official/crosswalk.csv（大觀一列）, data/processed/substations.geojson, data/processed/substation_dedup_log.csv（新增）, data/processed/plants.geojson, data/processed/dedup_log.csv, data/processed/stats.json
