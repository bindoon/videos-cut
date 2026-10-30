"""Delivery outcomes: actual encoded bytes, not trusted cache sidecars.

Browser/GPU smoke is separate: scripts/verify_codefilm.py. These tests need
only the same local FFmpeg/Pillow dependencies as the deterministic suite.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from videocut.codefilm import plan, sha256, verify_manifest
from videocut.ffmpeg_tools import invoke_json, parse_json_output


def dump(path, data):
    path.write_text(json.dumps(data))
    return path


def test_plan_is_read_only_and_fingerprints_inputs(tmp_path):
    film = tmp_path / "film"
    film.mkdir()
    (film / "index.html").write_text("<canvas></canvas>")
    dump(film / "timeline.json", {"fps": 24, "frames": 48, "duration": 2})
    config = dump(film / "codefilm.json", {
        "schema": "codefilm-v1", "timeline": "timeline.json", "sources": ["index.html"],
    })
    before = set(film.iterdir())
    original = plan(config)
    assert set(film.iterdir()) == before
    assert plan(config)["source_hash"] == original["source_hash"]
    (film / "index.html").write_text("<canvas>Changed scene</canvas>")
    assert plan(config)["source_hash"] != original["source_hash"]
    assert plan(config, width=640)["settings"]["height"] == 360
    with pytest.raises(ValueError, match="even"):
        plan(config, width=641)
    doc = json.loads(config.read_text())
    doc["sources"] = ["../outside.json"]
    dump(config, doc)
    with pytest.raises(ValueError, match="escapes"):
        plan(config)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    directory = tmp_path_factory.mktemp("codefilm-actual-media")
    frames = directory / "frames"
    frames.mkdir()
    for i in range(12):
        Image.new("RGB", (160, 90), (10 + i * 10, 70, 130)).save(frames / f"frame_{i:04d}.png")
    video = directory / "segment.mp4"
    invoke_json(["sequence", "--dir", str(frames), "--pattern", "frame_%04d.png", "--fps", "24", "-o", str(video), "--json"])
    manifest = {
        "schema": "codefilm-render-v1", "source_hash": "fixture", "width": 160, "height": 90,
        "fps": 24, "total_frames": 12, "start_frame": 0, "end_frame": 12, "frames": 12,
        "chunks": [{"a": 0, "b": 12, "file": str(video), "sha256": sha256(video)}],
    }
    return directory, video, manifest


def test_verify_real_frames_and_reject_corrupt_cache(rendered, tmp_path):
    _, video, manifest = rendered
    path = dump(tmp_path / "manifest.json", manifest)
    result = verify_manifest(path, video=video)
    assert result["passed"] and result["complete"] and result["frames"] == 12
    assert result["subtitle_sync"]["passed"] is None
    bad = tmp_path / "corrupt.mp4"
    payload = bytearray(video.read_bytes())
    payload[-1] ^= 1  # Same length: frame-count-only checks would miss this.
    bad.write_bytes(payload)
    changed = {**manifest, "chunks": [{**manifest["chunks"][0], "file": str(bad)}]}
    dump(path, changed)
    with pytest.raises(ValueError, match="checksum"):
        verify_manifest(path)


def test_verify_rejects_gap_partial_and_forged_metadata(rendered, tmp_path):
    _, _, manifest = rendered
    path = tmp_path / "manifest.json"
    dump(path, {**manifest, "chunks": [{**manifest["chunks"][0], "a": 1}]})
    with pytest.raises(ValueError, match="gap"):
        verify_manifest(path)
    dump(path, {**manifest, "total_frames": 24})
    with pytest.raises(ValueError, match="partial"):
        verify_manifest(path)
    assert verify_manifest(path, allow_partial=True)["complete"] is False
    # Actual media is 12 frames; inventing a 13-frame sidecar must not pass.
    dump(path, {**manifest, "total_frames": 13, "end_frame": 13, "frames": 13,
                "chunks": [{**manifest["chunks"][0], "b": 13}]})
    with pytest.raises(ValueError, match="nb_frames"):
        verify_manifest(path)


def test_tool_json_allows_only_declared_trailing_paths():
    assert parse_json_output('{"outputs":["/a.png"]}\n/a.png\n')["outputs"] == ["/a.png"]
    with pytest.raises(ValueError, match="non-JSON"):
        parse_json_output('{"outputs":["/a.png"]}\nUnexpected warning\n')


def test_hangzhou_audio_job_requires_output_and_preserves_delivery(tmp_path):
    script = Path(__file__).resolve().parents[1] / "films/hangzhou/tools/make_narration.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=False)
    assert result.returncode == 2 and "--output" in result.stderr
    delivered = tmp_path / "杭州-一城山水千年生长.mp4"
    delivered.write_bytes(b"previous delivery")
    result = subprocess.run([sys.executable, str(script), "--output", str(tmp_path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2 and "already contains a delivered film" in result.stderr
    assert delivered.read_bytes() == b"previous delivery"
    assert sorted(tmp_path.iterdir()) == [delivered]
