"""`make refresh` keeps the old OSM snapshot when the download fails (spec: data-refresh, Refresh command)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(shutil.which("make") is None or shutil.which("curl") is None,
                                reason="make and curl are required")


def test_failed_osm_download_keeps_previous_snapshot(tmp_path):
    snapshot = tmp_path / "taiwan-latest.osm.pbf"
    snapshot.write_bytes(b"previous snapshot")
    before = snapshot.stat().st_mtime_ns
    result = subprocess.run(
        ["make", "--no-print-directory", "-C", str(ROOT), "refresh", f"RAW={snapshot}",
         f"SNAPSHOT_URL={(tmp_path / 'missing.pbf').as_uri()}"],
        capture_output=True, text=True)
    assert result.returncode != 0
    assert snapshot.read_bytes() == b"previous snapshot"
    assert snapshot.stat().st_mtime_ns == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["taiwan-latest.osm.pbf"]  # no .new or .part left
    assert "powermap.official" not in result.stdout  # stopped before the official download
