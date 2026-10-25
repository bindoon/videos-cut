import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from videocut.media import duration, probe, run


def invoke(*arguments: str, cwd: Path, env=None):
    return subprocess.run(
        [sys.executable, "-m", "videocut", "ffmpeg", *arguments],
        check=False,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_ffmpeg_cli_cuts_from_another_directory_and_preserves_files(tmp_path: Path):
    source = tmp_path / "source with spaces.mp4"
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x284:rate=24:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ]
    )
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    target = tmp_path / "output with spaces.mp4"
    arguments = (
        "cut",
        source.name,
        "--start",
        "0.25",
        "--end",
        "1.5",
        "--accurate",
        "-o",
        target.name,
        "--json-brief",
    )
    planned = invoke(*arguments, "--dry-run", cwd=tmp_path)
    assert planned.returncode == 0, planned.stderr
    assert json.loads(planned.stdout)["dry_run"] is True
    assert not target.exists()

    edited = invoke(*arguments, cwd=tmp_path)
    assert edited.returncode == 0, edited.stderr
    assert json.loads(edited.stdout)["verified"] is True
    assert abs(duration(target) - 1.25) < 0.05
    streams = probe(target)["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}
    lengths = [float(s["duration"]) for s in streams]
    assert max(lengths) - min(lengths) < 0.05
    run(["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"])
    target_hash = hashlib.sha256(target.read_bytes()).hexdigest()

    refused = invoke(*arguments, cwd=tmp_path)
    assert refused.returncode == 1
    assert json.loads(refused.stdout)["error"]["reason"] == "output_exists"
    assert hashlib.sha256(target.read_bytes()).hexdigest() == target_hash
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


def test_ffmpeg_cli_help_and_listing_do_not_require_media_tools(tmp_path: Path):
    env = {**os.environ, "PATH": ""}
    listing = invoke("--list", cwd=tmp_path, env=env)
    assert listing.returncode == 0, listing.stderr
    assert len(set(listing.stdout.splitlines()) - {"doctor", "contract"}) == 42
    help_result = invoke("cut", "--help", cwd=tmp_path, env=env)
    assert help_result.returncode == 0, help_result.stderr
    assert "--accurate" in help_result.stdout
    unknown = invoke("../../arbitrary-script", cwd=tmp_path, env=env)
    assert unknown.returncode == 2
    assert "invalid choice" in unknown.stderr
