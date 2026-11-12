# Taiwan power map — data pipeline
# Usage: make data | make extract | make test | make clean

PY        := uv run python
RAW       := data/raw/taiwan-latest.osm.pbf
SEQ       := data/interim/power.geojsonseq
SUMMARY   := data/interim/extract_summary.json
FAC_META  := data/interim/facilities_meta.json
PLANTS    := data/processed/plants.geojson
LINES     := data/processed/lines.geojson
STATS     := data/processed/stats.json

# Tunable parameters (see design.md)
MAIN_BBOX            ?= 119.3,21.8,122.2,25.4
ROOFTOP_THRESHOLD_MW ?= 1
DEDUP_DISTANCE_M     ?= 500

.PHONY: all data extract test clean
all: data

data: $(STATS)

extract: $(SEQ)

# 1. Download (skipped when the snapshot already exists)
$(RAW):
	scripts/download.sh $@

# 2. Extract power features on the main island
$(SEQ): $(RAW) powermap/extract.py powermap/parsers.py Makefile
	$(PY) -m powermap.extract --input $(RAW) --output $(SEQ) --summary $(SUMMARY) --main-bbox=$(MAIN_BBOX)

# 3. Facilities
$(PLANTS): $(SEQ) powermap/facilities.py powermap/parsers.py powermap/geo.py Makefile
	$(PY) -m powermap.facilities --input $(SEQ) --output $(PLANTS) --dedup-log data/processed/dedup_log.csv --meta $(FAC_META) --rooftop-threshold-mw $(ROOFTOP_THRESHOLD_MW) --dedup-distance-m $(DEDUP_DISTANCE_M)

# 4. Lines
$(LINES): $(SEQ) powermap/lines.py powermap/parsers.py powermap/geo.py
	$(PY) -m powermap.lines --input $(SEQ) --output $(LINES)

# 5. Stats
$(STATS): $(PLANTS) $(LINES) $(SUMMARY) powermap/stats.py
	$(PY) -m powermap.stats --plants $(PLANTS) --lines $(LINES) --summary $(SUMMARY) --facilities-meta $(FAC_META) --output $(STATS)

test:
	uv run pytest

clean:
	find data/interim data/processed -type f ! -name .gitkeep -delete
