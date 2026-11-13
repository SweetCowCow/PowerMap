"""`make web` copies the committed data files (spec: web-map-publishing, Static site build)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB_FILES = ("plants.geojson", "lines.geojson", "substations.geojson", "official_points.geojson", "official_status.json",
             "stats.json", "official_diff.csv", "counties.geojson")

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")


def make_web(tmp_path, **overrides):
    args = ["make", "--no-print-directory", "-C", str(ROOT), "web", f"WEB_DATA={tmp_path / 'web-data'}"]
    args += [f"{k}={v}" for k, v in overrides.items()]
    return subprocess.run(args, capture_output=True, text=True)


def test_make_web_copies_eight_files_without_pipeline(tmp_path):
    missing = [name for name in WEB_FILES if not (ROOT / "data/processed" / name).exists()]
    if missing:
        pytest.skip(f"committed data missing: {missing}")
    result = make_web(tmp_path)
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in (tmp_path / "web-data").iterdir()) == sorted(WEB_FILES)
    assert "uv run" not in result.stdout  # no pipeline step ran


def test_make_web_fails_when_official_points_missing(tmp_path):
    result = make_web(tmp_path, OFFICIAL_POINTS=tmp_path / "missing" / "official_points.geojson")
    assert result.returncode != 0
    assert "official_points.geojson" in result.stderr


def test_make_web_fails_when_official_status_missing(tmp_path):
    result = make_web(tmp_path, OFFICIAL_STATUS=tmp_path / "missing" / "official_status.json")
    assert result.returncode != 0
    assert "official_status.json" in result.stderr
