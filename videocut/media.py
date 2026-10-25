from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def run(command: list[str], *, timeout: int = 900) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command, check=False, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode:
        raise RuntimeError(
            f"{command[0]} failed ({result.returncode}):\n{result.stderr[-6000:]}"
        )
    return result


def probe(path: Path) -> dict:
    return json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        ).stdout
    )


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def require_tools() -> None:
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            raise RuntimeError(f"Missing {binary}. macOS: brew install ffmpeg")


def decode_audio(
    path: Path,
    sample_rate: int = 16000,
    *,
    start: float | None = None,
    seconds: float | None = None,
):
    """Decode a mono float32 ASR input through our system FFmpeg.

    Passing a NumPy waveform is a supported faster-whisper input and avoids
    its 1.2.1 file decoder's incompatibility with PyAV 19 (upstream #1589).
    """
    import numpy as np

    if start is not None and start < 0 or seconds is not None and seconds <= 0:
        raise ValueError("Audio window start must be nonnegative and duration positive")
    command = ["ffmpeg", "-v", "error"]
    if start is not None:
        command += ["-ss", f"{start:.6f}"]
    command += ["-i", str(path)]
    if seconds is not None:
        command += ["-t", f"{seconds:.6f}"]
    command += [
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "pipe:1",
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        timeout=600,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-2000:])
    audio = np.frombuffer(result.stdout, dtype="<f4").copy()
    if not audio.size:
        raise ValueError(f"No audio samples: {path}")
    return audio


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
