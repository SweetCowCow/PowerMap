#!/usr/bin/env bash
# Download the Geofabrik Taiwan OSM snapshot.
# Usage: scripts/download.sh [target]   (default: data/raw/taiwan-latest.osm.pbf)
# Override the source with SNAPSHOT_URL=... ; skips when the target already exists.
set -euo pipefail

TARGET="${1:-data/raw/taiwan-latest.osm.pbf}"
URL="${SNAPSHOT_URL:-https://download.geofabrik.de/asia/taiwan-latest.osm.pbf}"

if [ -s "$TARGET" ]; then
  echo "Snapshot already present: $TARGET (delete it to re-download)"
  exit 0
fi

mkdir -p "$(dirname "$TARGET")"
TMP="$TARGET.part"
trap 'rm -f "$TMP"' EXIT

echo "Downloading $URL"
curl -fL --retry 3 --progress-bar -o "$TMP" "$URL"
mv "$TMP" "$TARGET"
trap - EXIT
echo "Saved $TARGET ($(du -h "$TARGET" | cut -f1))"
