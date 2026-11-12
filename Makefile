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
DEDUP_LOG := data/processed/dedup_log.csv
EXTRACT_OUT    := $(SEQ) $(SUMMARY)
FACILITIES_OUT := $(PLANTS) $(DEDUP_LOG) $(FAC_META)

# Tunable parameters (see design.md)
MAIN_BBOX            ?= 119.3,21.8,122.2,25.4
ROOFTOP_THRESHOLD_MW ?= 1
DEDUP_DISTANCE_M     ?= 500

# Parameter stamps, checked while make reads this file (before it looks at any
# timestamps). When a value differs from the last run, the stamp is rewritten and
# the outputs of that step and later steps are back-dated to 2000, so `make data
# DEDUP_DISTANCE_M=300` rebuilds them. Back-dating (not relying on the stamp being
# newer) matters because make 3.81 compares whole seconds and the pipeline is fast.
EXTRACT_PARAMS    := data/interim/extract.params
FACILITIES_PARAMS := data/interim/facilities.params
mark_stale_if_changed = $(shell mkdir -p $(dir $(1)); [ "$$(cat $(1) 2>/dev/null)" = "$(2)" ] \
	|| { echo "$(2)" > $(1); for f in $(3); do [ -f "$$f" ] && touch -t 200001010000 "$$f"; done; })
$(call mark_stale_if_changed,$(EXTRACT_PARAMS),MAIN_BBOX=$(MAIN_BBOX),$(EXTRACT_OUT) $(FACILITIES_OUT) $(LINES) $(STATS))
$(call mark_stale_if_changed,$(FACILITIES_PARAMS),ROOFTOP_THRESHOLD_MW=$(ROOFTOP_THRESHOLD_MW) DEDUP_DISTANCE_M=$(DEDUP_DISTANCE_M),$(FACILITIES_OUT) $(STATS))

.PHONY: all data extract test clean
all: data

data: $(STATS)

extract: $(EXTRACT_OUT)

# Steps with several outputs use multi-target pattern rules (stem "data"): make 3.81,
# the macOS default, then runs the recipe once and reruns it when any output is
# missing. Downstream steps depend on all outputs of a step for the same reason.

# 1. Download (skipped when the snapshot already exists)
$(RAW):
	scripts/download.sh $@

# 2. Extract power features on the main island
%/interim/power.geojsonseq %/interim/extract_summary.json: $(RAW) $(EXTRACT_PARAMS) powermap/extract.py powermap/osm.py powermap/parsers.py Makefile
	$(PY) -m powermap.extract --input $(RAW) --output $(SEQ) --summary $(SUMMARY) --main-bbox=$(MAIN_BBOX)

# 3. Facilities
%/processed/plants.geojson %/processed/dedup_log.csv %/interim/facilities_meta.json: $(EXTRACT_OUT) $(FACILITIES_PARAMS) powermap/facilities.py powermap/osm.py powermap/parsers.py powermap/geo.py Makefile
	$(PY) -m powermap.facilities --input $(SEQ) --output $(PLANTS) --dedup-log $(DEDUP_LOG) --meta $(FAC_META) --rooftop-threshold-mw $(ROOFTOP_THRESHOLD_MW) --dedup-distance-m $(DEDUP_DISTANCE_M)

# 4. Lines
$(LINES): $(EXTRACT_OUT) powermap/lines.py powermap/osm.py powermap/parsers.py powermap/geo.py Makefile
	$(PY) -m powermap.lines --input $(SEQ) --output $(LINES)

# 5. Stats
$(STATS): $(EXTRACT_OUT) $(FACILITIES_OUT) $(LINES) powermap/stats.py Makefile
	$(PY) -m powermap.stats --plants $(PLANTS) --lines $(LINES) --summary $(SUMMARY) --facilities-meta $(FAC_META) --output $(STATS)

test:
	uv run pytest

clean:
	find data/interim data/processed -type f ! -name .gitkeep -delete
