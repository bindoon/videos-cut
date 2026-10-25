"""Reproducible smoke checks for optional FFmpeg capabilities, using synthetic media.

Run with: uv run python scripts/verify_ffmpeg_tools.py --output outputs/ffmpeg-smoke
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", default="Heiti SC")
    parser.add_argument("--fonts-dir", default="/System/Library/Fonts")
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    commands = []

    def execute(name: str, command: list[str], *, binary=False):
        result = subprocess.run(command, check=False, capture_output=True, timeout=180)
        commands.append(
            {"name": name, "argv": command, "returncode": result.returncode}
        )
        (folder / "commands.json").write_text(json.dumps(commands, indent=2))
        (folder / f"{name}.stderr.txt").write_bytes(result.stderr)
        if not binary:
            (folder / f"{name}.json").write_bytes(result.stdout)
        if result.returncode:
            raise RuntimeError(f"{name} failed; see {folder / f'{name}.stderr.txt'}")
        return result.stdout if binary else json.loads(result.stdout or "{}")

    def tool(name: str, *arguments: str):
        print(f"Checking {name}", flush=True)
        return execute(
            name,
            [sys.executable, "-m", "videocut", "ffmpeg", name, *arguments, "--json"],
        )

    doctor = tool("doctor")
    ffmpeg = doctor["ffmpeg_path"]
    source, music = folder / "source.mp4", folder / "music.wav"
    voice = (
        "aevalsrc=0.25*sin(2*PI*440*t)*"
        "if(between(t\\,1\\,2.5)+between(t\\,3.5\\,5)\\,1\\,0):s=48000:d=6"
    )
    execute(
        "source-fixture",
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x18334a:s=480x854:r=24:d=6",
            "-f",
            "lavfi",
            "-i",
            voice,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-shortest",
            str(source),
        ],
    )
    execute(
        "music-fixture",
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000:duration=6",
            str(music),
        ],
    )
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    srt = folder / "captions.srt"
    srt.write_text(
        "1\n00:00:00,500 --> 00:00:02,500\n扩展工具本地验证\n\n"
        "2\n00:00:03,500 --> 00:00:05,500\n中文字幕与配乐\n",
        encoding="utf-8",
    )
    captioned, mixed, delivery = (
        folder / f"{name}.mp4" for name in ("captioned", "mixed", "youtube")
    )
    tool(
        "caption",
        str(source),
        "--srt",
        str(srt),
        "--font",
        args.font,
        "--fonts-dir",
        args.fonts_dir,
        "--size",
        "28",
        "-o",
        str(captioned),
    )
    tool("audio", str(captioned), "--music", str(music), "--duck", "-o", str(mixed))
    tool(
        "export", str(mixed), "--preset", "youtube", "--normalize", "-o", str(delivery)
    )
    check = tool("check", str(delivery), "--platform", "youtube")
    tool(
        "look",
        str(captioned),
        "--tiles",
        "3x2",
        "-o",
        str(folder / "contact-sheet.png"),
    )

    # Synthetic 10-bit PQ tags exercise the HDR path, not a real camera's colour quality.
    hdr, sdr = folder / "synthetic-pq.mp4", folder / "sdr.mp4"
    execute(
        "hdr-fixture",
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=24:duration=1,format=yuv420p10le",
            "-c:v",
            "libx265",
            "-preset",
            "ultrafast",
            "-x265-params",
            "log-level=error:pools=2:colorprim=9:transfer=16:colormatrix=9",
            "-tag:v",
            "hvc1",
            "-color_primaries",
            "bt2020",
            "-color_trc",
            "smpte2084",
            "-colorspace",
            "bt2020nc",
            str(hdr),
        ],
    )
    hdr_probe = execute(
        "hdr-probe",
        [sys.executable, "-m", "videocut", "ffmpeg", "probe", str(hdr), "--json"],
    )
    assert hdr_probe["video"]["hdr"] is True
    assert hdr_probe["video"]["color_transfer"] == "smpte2084"
    tool("color", str(hdr), "--to-sdr", "-o", str(sdr))
    sdr_probe = tool("probe", str(sdr))
    assert sdr_probe["video"]["hdr"] is False
    assert sdr_probe["video"]["color_transfer"] == "bt709"

    # Inspect actual encoded pixels, not the caption tool's own reported timestamps.
    white_pixels = {}
    for when in (0.25, 1.5, 3.0, 4.5, 5.75):
        data = execute(
            f"caption-pixels-{when}",
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                str(when),
                "-i",
                str(captioned),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            binary=True,
        )
        pixels = np.frombuffer(data, dtype=np.uint8).reshape(854, 480, 3)
        white_pixels[str(when)] = int(np.all(pixels > 200, axis=2).sum())
    assert white_pixels["1.5"] > 100 and white_pixels["4.5"] > 100
    assert all(white_pixels[str(t)] == 0 for t in (0.25, 3.0, 5.75))

    data = execute(
        "mixed-audio",
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(mixed),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-f",
            "f32le",
            "pipe:1",
        ],
        binary=True,
    )
    waveform = np.frombuffer(data, dtype="<f4")

    def music_amplitude(start: float, end: float) -> float:
        samples = waveform[round(start * 48000) : round(end * 48000)]
        tone = np.exp(-2j * np.pi * 1000 * np.arange(len(samples)) / 48000)
        return float(abs(np.dot(samples, tone)) / len(samples))

    quiet = music_amplitude(0.25, 0.75)
    active = music_amplitude(1.5, 2.25)
    assert active < quiet * 0.8, (active, quiet)
    execute(
        "full-decode", [ffmpeg, "-v", "error", "-i", str(delivery), "-f", "null", "-"]
    )
    assert check["ok"] is True and check["failed"] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    report = {
        "synthetic_fixture": True,
        "note": "440 Hz pulses stand in for a ducking sidechain; no real speech or ASR is used.",
        "ffmpeg": doctor["ffmpeg"],
        "ffmpeg_path": ffmpeg,
        "synthetic_pq_to_sdr": sdr_probe["video"],
        "caption_white_pixels": white_pixels,
        "music_amplitude_quiet": quiet,
        "music_amplitude_active": active,
        "music_duck_db": float(20 * np.log10(active / quiet)),
        "delivery_checks": check["checks"],
        "source_unchanged": True,
        "full_decode": "passed",
    }
    (folder / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(f"Passed: {folder / 'verification.json'}")


if __name__ == "__main__":
    main()
