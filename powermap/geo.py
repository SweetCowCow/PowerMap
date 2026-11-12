"""Coordinate transforms between WGS84 (EPSG:4326) and TWD97 / TM2 (EPSG:3826)."""

import shapely
from pyproj import Transformer

_TO_3826 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)


def to_3826(geom):
    """Project a lon/lat geometry to metres (EPSG:3826)."""
    return shapely.transform(geom, lambda x, y: _TO_3826.transform(x, y), interleaved=False)


def to_4326(geom):
    """Project an EPSG:3826 geometry back to lon/lat."""
    return shapely.transform(geom, lambda x, y: _TO_4326.transform(x, y), interleaved=False)
