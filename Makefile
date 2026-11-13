# Taiwan power map — data pipeline
# Usage: make data | make extract | make test | make clean | make refresh
#        make official-download | make crosswalk-candidates
#        make boundaries | make web | make test-web | make all

PY        := uv run python
RAW       := data/raw/taiwan-latest.osm.pbf
SEQ       := data/interim/power.geojsonseq
SUMMARY   := data/interim/extract_summary.json
FAC_OSM   := data/interim/facilities_osm.geojson
DEDUP_OSM := data/interim/dedup_log_osm.csv
FAC_META  := data/interim/facilities_meta.json
OFFICIAL  := data/interim/official_plants.json
ENRICH_META := data/interim/enrich_meta.json
PLANTS    := data/processed/plants.geojson
DEDUP_LOG := data/processed/dedup_log.csv
UNMATCHED := data/processed/unmatched.csv
DIFF      := data/processed/official_diff.csv
LINES     := data/processed/lines.geojson
SUBSTATIONS := data/processed/substations.geojson
SUB_DEDUP_LOG := data/processed/substation_dedup_log.csv
OFFICIAL_POINTS := data/processed/official_points.geojson
OFFICIAL_STATUS := data/processed/official_status.json
STATS     := data/processed/stats.json
CROSSWALK := data/official/crosswalk.csv
LOCATIONS := data/official/locations.csv
STATUS_TABLE := data/official/status.csv
CANDIDATES := data/official/crosswalk_candidates.csv
BOUNDARY_ZIP := data/raw/boundaries/counties.zip
COUNTIES  := data/processed/counties.geojson
EXTRACT_OUT    := $(SEQ) $(SUMMARY)
FACILITIES_OUT := $(FAC_OSM) $(DEDUP_OSM) $(FAC_META)
ENRICH_OUT     := $(PLANTS) $(DEDUP_LOG) $(UNMATCHED) $(DIFF) $(ENRICH_META)

# Tunable parameters (see design.md)
MAIN_BBOX               ?= 119.3,21.8,122.2,25.4
ROOFTOP_THRESHOLD_MW    ?= 1
DEDUP_DISTANCE_M        ?= 500
CAPACITY_DIFF_THRESHOLD ?= 0.2
# County boundary SHP zip (data.gov.tw 7442); default in powermap/boundaries.py
BOUNDARY_URL            ?=
# Official snapshot directory; default: the latest data/official/raw/<YYYY-MM-DD>
OFFICIAL_DIR            ?= $(lastword $(sort $(wildcard data/official/raw/????-??-??)))

# Parameter stamps, checked while make reads this file (before it looks at any
# timestamps). When a value differs from the last run, the stamp is rewritten and
# the outputs of that step and later steps are back-dated to 2000, so `make data
# DEDUP_DISTANCE_M=300` rebuilds them. Back-dating (not relying on the stamp being
# newer) matters because make 3.81 compares whole seconds and the pipeline is fast.
EXTRACT_PARAMS    := data/interim/extract.params
FACILITIES_PARAMS := data/interim/facilities.params
OFFICIAL_PARAMS   := data/interim/official.params
ENRICH_PARAMS     := data/interim/enrich.params
mark_stale_if_changed = $(shell mkdir -p $(dir $(1)); [ "$$(cat $(1) 2>/dev/null)" = "$(2)" ] \
	|| { echo "$(2)" > $(1); for f in $(3); do [ -f "$$f" ] && touch -t 200001010000 "$$f"; done; })
$(call mark_stale_if_changed,$(EXTRACT_PARAMS),MAIN_BBOX=$(MAIN_BBOX),$(EXTRACT_OUT) $(FACILITIES_OUT) $(ENRICH_OUT) $(LINES) $(SUBSTATIONS) $(SUB_DEDUP_LOG) $(OFFICIAL_POINTS) $(STATS))
$(call mark_stale_if_changed,$(FACILITIES_PARAMS),ROOFTOP_THRESHOLD_MW=$(ROOFTOP_THRESHOLD_MW) DEDUP_DISTANCE_M=$(DEDUP_DISTANCE_M),$(FACILITIES_OUT) $(ENRICH_OUT) $(STATS))
$(call mark_stale_if_changed,$(OFFICIAL_PARAMS),OFFICIAL_DIR=$(OFFICIAL_DIR),$(OFFICIAL) $(ENRICH_OUT) $(STATS))
$(call mark_stale_if_changed,$(ENRICH_PARAMS),CAPACITY_DIFF_THRESHOLD=$(CAPACITY_DIFF_THRESHOLD),$(ENRICH_OUT) $(STATS))

.PHONY: all data extract test clean official-download crosswalk-candidates boundaries web test-web refresh
# Sequential on purpose: under `make -j`, `web` would otherwise copy data before `data` rewrites it.
all:
	$(MAKE) data
	$(MAKE) web

data: $(STATS) $(OFFICIAL_STATUS)

extract: $(EXTRACT_OUT)

# Steps with several outputs use multi-target pattern rules (stem "data" or
# "data/interim"): make 3.81, the macOS default, then runs the recipe once and reruns
# it when any output is missing. Downstream steps depend on all outputs of a step
# for the same reason.

# 1. Download the OSM snapshot (skipped when it already exists)
$(RAW):
	scripts/download.sh $@

# 2. Extract power features on the main island
%/interim/power.geojsonseq %/interim/extract_summary.json: $(RAW) $(EXTRACT_PARAMS) powermap/extract.py powermap/osm.py powermap/parsers.py Makefile
	$(PY) -m powermap.extract --input $(RAW) --output $(SEQ) --summary $(SUMMARY) --main-bbox=$(MAIN_BBOX)

# 3. Facilities from OSM only
%/facilities_osm.geojson %/dedup_log_osm.csv %/facilities_meta.json: $(EXTRACT_OUT) $(FACILITIES_PARAMS) powermap/facilities.py powermap/osm.py powermap/parsers.py powermap/geo.py Makefile
	$(PY) -m powermap.facilities --input $(SEQ) --output $(FAC_OSM) --dedup-log $(DEDUP_OSM) --meta $(FAC_META) --rooftop-threshold-mw $(ROOFTOP_THRESHOLD_MW) --dedup-distance-m $(DEDUP_DISTANCE_M)

# 4. Official plant list from the committed snapshot (no network)
$(OFFICIAL): $(wildcard $(OFFICIAL_DIR)/*) $(OFFICIAL_PARAMS) powermap/official.py powermap/crosswalk.py powermap/parsers.py Makefile
	$(PY) -m powermap.official normalize $(if $(OFFICIAL_DIR),--raw-dir $(OFFICIAL_DIR)) --output $(OFFICIAL)

# 5. Enrich facilities with official plants through the reviewed crosswalk
%/processed/plants.geojson %/processed/dedup_log.csv %/processed/unmatched.csv %/processed/official_diff.csv %/interim/enrich_meta.json: $(FACILITIES_OUT) $(OFFICIAL) $(wildcard $(CROSSWALK)) $(ENRICH_PARAMS) powermap/enrich.py powermap/crosswalk.py powermap/facilities.py powermap/geo.py Makefile
	$(PY) -m powermap.enrich --facilities $(FAC_OSM) --dedup-log-osm $(DEDUP_OSM) --official $(OFFICIAL) --crosswalk $(CROSSWALK) --output $(PLANTS) --dedup-log $(DEDUP_LOG) --unmatched $(UNMATCHED) --diff $(DIFF) --meta $(ENRICH_META) --capacity-diff-threshold $(CAPACITY_DIFF_THRESHOLD)

# 6. Lines
$(LINES): $(EXTRACT_OUT) powermap/lines.py powermap/osm.py powermap/parsers.py powermap/geo.py Makefile
	$(PY) -m powermap.lines --input $(SEQ) --output $(LINES)

# 7. Substations
%/processed/substations.geojson %/processed/substation_dedup_log.csv: $(EXTRACT_OUT) powermap/substations.py powermap/facilities.py powermap/osm.py powermap/parsers.py powermap/geo.py Makefile
	$(PY) -m powermap.substations --input $(SEQ) --output $(SUBSTATIONS) --dedup-log $(SUB_DEDUP_LOG)

# 8. Estimated official locations (reviewed by hand in data/official/locations.csv)
$(OFFICIAL_POINTS): $(OFFICIAL) $(wildcard $(CROSSWALK)) $(wildcard $(LOCATIONS)) powermap/official_points.py powermap/extract.py Makefile
	$(PY) -m powermap.official_points --official $(OFFICIAL) --crosswalk $(CROSSWALK) --locations $(LOCATIONS) --output $(OFFICIAL_POINTS) --main-bbox=$(MAIN_BBOX)

# 9. Operating status (reviewed by hand in data/official/status.csv)
$(OFFICIAL_STATUS): $(OFFICIAL) $(wildcard $(STATUS_TABLE)) powermap/official_status.py Makefile
	$(PY) -m powermap.official_status --official $(OFFICIAL) --status $(STATUS_TABLE) --output $(OFFICIAL_STATUS)

# 10. Stats
$(STATS): $(EXTRACT_OUT) $(FACILITIES_OUT) $(OFFICIAL) $(ENRICH_OUT) $(LINES) $(SUBSTATIONS) $(SUB_DEDUP_LOG) $(OFFICIAL_POINTS) powermap/stats.py Makefile
	$(PY) -m powermap.stats --plants $(PLANTS) --lines $(LINES) --substations $(SUBSTATIONS) --summary $(SUMMARY) --facilities-meta $(FAC_META) --official $(OFFICIAL) --dedup-log $(DEDUP_LOG) --diff $(DIFF) --unmatched $(UNMATCHED) --official-points $(OFFICIAL_POINTS) --output $(STATS)

# Official open data snapshot (network; creates data/official/raw/<date>/, commit it)
official-download:
	$(PY) -m powermap.official download --dest data/official/raw

# Monthly refresh (network): new OSM snapshot (kept only when the download succeeds), today's
# official snapshot (reused when it already exists), rebuild, then a report comparing the
# outputs with the last commit. Review the report before committing. SNAPSHOT_URL overrides
# the Geofabrik source (see scripts/download.sh).
REFRESH_REPORT := data/interim/refresh_report.md
refresh:
	rm -f $(RAW).new
	scripts/download.sh $(RAW).new
	mv $(RAW).new $(RAW)
	$(PY) -m powermap.official download --dest data/official/raw --reuse-existing
	$(MAKE) data
	$(PY) -m powermap.refresh_report --base-ref HEAD --output $(REFRESH_REPORT)

# Candidate pairs for reviewing data/official/crosswalk.csv by hand
crosswalk-candidates: $(FACILITIES_OUT) $(OFFICIAL) powermap/crosswalk.py
	$(PY) -m powermap.crosswalk --official $(OFFICIAL) --facilities $(FAC_OSM) --output $(CANDIDATES)

# County boundaries for the web base layer (network; not part of `make data`; commit the output)
boundaries:
	$(PY) -m powermap.boundaries --zip $(BOUNDARY_ZIP) --output $(COUNTIES) $(if $(BOUNDARY_URL),--url "$(BOUNDARY_URL)")

# Static site: copy committed data into web/data/. Deliberately has no prerequisites on
# pipeline outputs, so it never triggers the pipeline (CI has no OSM snapshot and the
# parameter stamps above back-date outputs on a fresh checkout).
WEB_DATA  := web/data
WEB_FILES := $(PLANTS) $(LINES) $(SUBSTATIONS) $(OFFICIAL_POINTS) $(OFFICIAL_STATUS) $(STATS) $(DIFF) $(COUNTIES)
web:
	mkdir -p $(WEB_DATA)
	cp $(WEB_FILES) $(WEB_DATA)/

test-web:
	node --test web/tests/*.test.js

test:
	uv run pytest

clean:
	find data/interim data/processed -type f ! -name .gitkeep -delete
