"""Tests for scripts/download.sh (spec: osm-power-extraction, snapshot download)."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "download.sh"


def run(target, url):
    env = {**os.environ, "SNAPSHOT_URL": url}
    return subprocess.run(["bash", str(SCRIPT), str(target)], env=env, capture_output=True, text=True)


def test_downloads_to_target(tmp_path):
    source = tmp_path / "src.pbf"
    source.write_bytes(b"pbf-bytes")
    target = tmp_path / "raw" / "x.osm.pbf"
    result = run(target, source.as_uri())
    assert result.returncode == 0
    assert target.read_bytes() == b"pbf-bytes"
    assert not Path(f"{target}.part").exists()


def test_existing_snapshot_is_kept(tmp_path):
    target = tmp_path / "x.osm.pbf"
    target.write_bytes(b"old")
    result = run(target, (tmp_path / "missing.pbf").as_uri())
    assert result.returncode == 0 and "already present" in result.stdout
    assert target.read_bytes() == b"old"


def test_failed_download_leaves_no_file(tmp_path):
    target = tmp_path / "x.osm.pbf"
    result = run(target, (tmp_path / "missing.pbf").as_uri())
    assert result.returncode != 0
    assert not target.exists() and not Path(f"{target}.part").exists()
