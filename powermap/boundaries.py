"""Download and simplify the national county boundaries for the web map base layer.

Implements the ``county-boundary-dataset`` spec.

Usage::

    python -m powermap.boundaries --zip data/raw/boundaries/counties.zip \
        --output data/processed/counties.geojson [--url URL]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import mapping

DATASET = "data.gov.tw/7442"
DEFAULT_URL = ("https://www.tgos.tw/tgos/VirtualDir/Product/1cd4f4c9-6b01-4cf9-bf6c-23a73aa17d24/"
               "直轄市、縣(市)界線1140318.zip")
LICENSE = "政府資料開放授權條款第1版"
EXCLUDED_COUNTIES = ("澎湖縣", "金門縣", "連江縣")
NAME_FIELD = "COUNTYNAME"
SIMPLIFY_TOLERANCE_M = 100
DECIMALS = 5
USER_AGENT = "powermap/0.1 (open data pipeline)"


class BoundaryError(Exception):
    """Raised when the boundary source cannot be downloaded or read."""


def _quote_url(url: str) -> str:
    """Percent-encode non-ASCII characters (the TGOS file name is Chinese)."""
    return urllib.parse.quote(url, safe=":/?&=%#")


def url_record(zip_path: str | Path) -> Path:
    """Sidecar file that records which URL a zip was downloaded from."""
    zip_path = Path(zip_path)
    return zip_path.with_name(zip_path.name + ".url")


def recorded_url(zip_path: str | Path) -> str | None:
    record = url_record(zip_path)
    return record.read_text(encoding="utf-8").strip() if record.exists() else None


def download(url: str, target: str | Path) -> bool:
    """Download ``url`` to ``target`` unless it exists. Returns True when downloaded.

    The source URL is written next to the zip (``<zip>.url``) so provenance stays tied to
    the file actually used, not to whatever URL a later run passes.
    """
    target = Path(target)
    if target.exists() and target.stat().st_size > 0:
        recorded = recorded_url(target)
        if recorded is not None and recorded != url:
            raise BoundaryError(f"{target} was downloaded from {recorded}; delete it (and {url_record(target).name}) "
                                f"to download {url}")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        request = urllib.request.Request(_quote_url(url), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as out:
            while chunk := response.read(1 << 16):
                out.write(chunk)
        part.rename(target)
        url_record(target).write_text(url + "\n", encoding="utf-8")
    except BaseException as exc:
        part.unlink(missing_ok=True)
        if isinstance(exc, (urllib.error.URLError, OSError)):
            raise BoundaryError(f"download failed: {url}: {exc}") from exc
        raise
    return True


def _round_coords(geom, decimals: int = DECIMALS):
    return shapely.transform(geom, lambda xy: np.round(xy, decimals))


def build(zip_path: str | Path, url: str, name_field: str = NAME_FIELD) -> dict:
    """Read the county SHP zip and return the simplified FeatureCollection."""
    zip_path = Path(zip_path)
    try:
        gdf = gpd.read_file(f"zip://{zip_path.resolve()}")
    except Exception as exc:  # pyogrio raises its own error types
        raise BoundaryError(f"cannot read {zip_path}: {exc}") from exc
    if name_field not in gdf.columns:
        raise BoundaryError(f"field {name_field!r} not found; columns: {list(gdf.columns)}")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf[~gdf[name_field].isin(EXCLUDED_COUNTIES)]
    simplified = gdf.to_crs("EPSG:3826").simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True).to_crs("EPSG:4326")

    features = []
    for name, geom in zip(gdf[name_field], simplified):
        features.append({
            "type": "Feature",
            "properties": {"name": name},
            "geometry": mapping(_round_coords(geom)),
        })
    features.sort(key=lambda f: f["properties"]["name"])

    data = zip_path.read_bytes()
    downloaded_at = datetime.fromtimestamp(zip_path.stat().st_mtime, timezone.utc)
    return {
        "type": "FeatureCollection",
        "source": {
            "dataset": DATASET,
            "url": url,
            "downloaded_at": downloaded_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "license": LICENSE,
        },
        "features": features,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zip", required=True, help="local path of the SHP zip (downloaded when missing)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args(argv)

    try:
        if download(args.url, args.zip):
            print(f"Downloaded {args.zip}")
        else:
            print(f"Boundary zip already present: {args.zip} (delete it to re-download)")
        # Provenance follows the zip actually used (a zip from before URL records keeps the passed URL).
        collection = build(args.zip, recorded_url(args.zip) or args.url)
    except BoundaryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {output}: {len(collection['features'])} counties, {output.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
