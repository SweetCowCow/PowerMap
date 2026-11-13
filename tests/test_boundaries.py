"""Tests for powermap.boundaries (spec: county-boundary-dataset)."""

import hashlib
import json
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from powermap.boundaries import BoundaryError, build, download, main, recorded_url

COUNTIES = {
    "臺北市": (121.5, 25.0),
    "高雄市": (120.3, 22.6),
    "澎湖縣": (119.6, 23.5),
    "金門縣": (118.3, 24.4),
    "連江縣": (119.95, 26.15),
}


def _square(lon, lat, size=0.123456789):
    return Polygon([(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size)])


def make_zip(tmp_path):
    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    gdf = gpd.GeoDataFrame(
        {
            "COUNTYNAME": list(COUNTIES),
            "COUNTYCODE": [str(i) for i in range(len(COUNTIES))],
            "COUNTYENG": [f"County {i}" for i in range(len(COUNTIES))],
        },
        geometry=[_square(*xy) for xy in COUNTIES.values()],
        crs="EPSG:4326",
    )
    gdf.to_file(shp_dir / "COUNTY_MOI.shp", engine="pyogrio", encoding="utf-8")
    zip_path = tmp_path / "src" / "counties.zip"
    zip_path.parent.mkdir()
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in shp_dir.iterdir():
            zf.write(f, f.name)
    return zip_path


def _coords(geometry):
    def walk(x):
        if isinstance(x, (int, float)):
            yield x
        else:
            for item in x:
                yield from walk(item)
    return list(walk(geometry["coordinates"]))


def test_outlying_counties_dropped_and_only_name(tmp_path):
    zip_path = make_zip(tmp_path)
    result = build(zip_path, "file:///x.zip")
    names = [f["properties"]["name"] for f in result["features"]]
    assert sorted(names) == ["臺北市", "高雄市"]
    for f in result["features"]:
        assert f["properties"] == {"name": f["properties"]["name"]}


def test_coordinates_rounded_to_five_decimals(tmp_path):
    result = build(make_zip(tmp_path), "file:///x.zip")
    for f in result["features"]:
        for value in _coords(f["geometry"]):
            assert round(value, 5) == value


def test_source_provenance(tmp_path):
    zip_path = make_zip(tmp_path)
    result = build(zip_path, "https://example.test/c.zip")
    source = result["source"]
    assert source["dataset"] == "data.gov.tw/7442"
    assert source["url"] == "https://example.test/c.zip"
    assert source["sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert source["license"] == "政府資料開放授權條款第1版"
    assert source["downloaded_at"].endswith("Z")


def test_download_skips_existing(tmp_path):
    target = tmp_path / "raw" / "counties.zip"
    target.parent.mkdir()
    target.write_bytes(b"existing")
    # URL would fail if fetched
    assert download((tmp_path / "missing.zip").as_uri(), target) is False
    assert target.read_bytes() == b"existing"


def test_download_failure_leaves_no_file(tmp_path):
    target = tmp_path / "raw" / "counties.zip"
    with pytest.raises(BoundaryError):
        download((tmp_path / "missing.zip").as_uri(), target)
    assert list(target.parent.iterdir()) == []


def test_main_end_to_end(tmp_path):
    src = make_zip(tmp_path)
    target = tmp_path / "raw" / "counties.zip"
    output = tmp_path / "out" / "counties.geojson"
    assert main(["--zip", str(target), "--output", str(output), "--url", src.as_uri()]) == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data["features"]) == 2
    assert data["source"]["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


def test_main_download_failure_exit_code(tmp_path, capsys):
    target = tmp_path / "raw" / "counties.zip"
    output = tmp_path / "out" / "counties.geojson"
    code = main(["--zip", str(target), "--output", str(output), "--url", (tmp_path / "nope.zip").as_uri()])
    assert code == 1
    assert not target.exists()
    assert not output.exists()
    assert "download failed" in capsys.readouterr().err


def test_download_records_source_url(tmp_path):
    src = make_zip(tmp_path)
    target = tmp_path / "raw" / "counties.zip"
    assert download(src.as_uri(), target) is True
    assert recorded_url(target) == src.as_uri()


def test_existing_zip_from_other_url_is_rejected(tmp_path):
    src = make_zip(tmp_path)
    target = tmp_path / "raw" / "counties.zip"
    download(src.as_uri(), target)
    with pytest.raises(BoundaryError, match="delete it"):
        download("https://example.test/newer.zip", target)
    assert download(src.as_uri(), target) is False  # same URL: reuse the zip


def test_main_provenance_follows_recorded_url(tmp_path):
    src = make_zip(tmp_path)
    target = tmp_path / "raw" / "counties.zip"
    output = tmp_path / "out" / "counties.geojson"
    assert main(["--zip", str(target), "--output", str(output), "--url", src.as_uri()]) == 0
    assert main(["--zip", str(target), "--output", str(output), "--url", "https://example.test/newer.zip"]) == 1
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["source"]["url"] == src.as_uri()
