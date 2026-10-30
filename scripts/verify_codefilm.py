"""Opt-in local Chromium/FFmpeg smoke; no GIS downloads or voice models.

Install examples/codefilm's npm dependencies first. The normal pytest suite
checks byte integrity with FFmpeg without requiring a browser installation.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from videocut.codefilm import sha256
from videocut.ffmpeg_tools import invoke_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Choose a new output directory for the smoke")
    output.mkdir(parents=True)
    command = [sys.executable, "-m", "videocut.codefilm", "render", "--config",
               str(ROOT / "examples/codefilm/codefilm.json"), "--output", str(output)]
    if args.browser:
        command += ["--browser", args.browser]

    def run(argv, log, *, ok=True):
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
        (output / log).write_text(result.stdout + result.stderr)
        if ok and result.returncode:
            raise RuntimeError(f"Smoke failed: {log}\n{result.stdout[-1500:]}\n{result.stderr[-1500:]}")
        return result

    run(command, "render.log")
    manifest = json.loads((output / "render-manifest.json").read_text())
    assert manifest["frames"] == 48 and len(manifest["chunks"]) == 4
    chunks = [Path(c["file"]) for c in manifest["chunks"]]
    before = [(sha256(p), p.stat().st_mtime_ns) for p in chunks]
    resumed = run(command, "resume.log")
    assert resumed.stdout.count("CACHED ") == 4
    assert [(sha256(p), p.stat().st_mtime_ns) for p in chunks] == before
    # Deliberately damage a same-sized generated segment: resume must reject it.
    original = chunks[0].read_bytes()
    damaged = bytearray(original)
    damaged[-1] ^= 1
    try:
        chunks[0].write_bytes(damaged)
        rejected = run(command, "corruption-rejection.log", ok=False)
        assert rejected.returncode != 0 and "checksum mismatch" in rejected.stderr
    finally:
        chunks[0].write_bytes(original)

    run([sys.executable, "-m", "videocut.codefilm", "verify", str(output / "render-manifest.json"),
         "--report", str(output / "manifest-verification.json")], "verify.log")
    still_command = command.copy()
    still_command[3] = "stills"
    run(still_command, "stills.log")
    stills = json.loads((output / "latest-stills.json").read_text())
    assert stills["deterministic_same_frame"] and len(stills["stills"]) == 2
    listing = output / "segments.txt"
    listing.write_text("\n".join(map(str, chunks)) + "\n")
    video = output / "smoke.mp4"
    operation = ["join", "--list", str(listing), "--transition", "none", "-o", str(video)]
    invoke_json([*operation, "--dry-run", "--json"], report=output / "join-plan.json")
    invoke_json([*operation, "--json"], report=output / "join-result.json")
    run([sys.executable, "-m", "videocut.codefilm", "verify", str(output / "render-manifest.json"),
         "--video", str(video), "--report", str(output / "movie-verification.json")], "movie-verify.log")
    invoke_json(["look", str(video), "--tiles", "3x2", "-o", str(output / "contact-sheet.png"), "--json"],
                report=output / "look.json")
    print(json.dumps({"passed": True, "frames": 48, "chunks_reused": 4,
                      "corrupt_cache_rejected": True, "video": str(video),
                      "contact_sheet": str(output / "contact-sheet.png")}, indent=2))


if __name__ == "__main__":
    main()
