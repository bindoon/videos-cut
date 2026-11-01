"""Verify the actual final artifact, including OCR once for every caption cue.

Checks here are separate from the original pipeline's Qwen/sync.py gate.
"""
from __future__ import annotations

from paths import output_directory

import hashlib
import json
import pathlib
import re
import subprocess
import wave

import numpy as np
from scipy.signal import correlate
from videocut.ffmpeg_tools import invoke_json

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = None
FILM = ROOT / "films/hangzhou"


def run(args, report):
    return invoke_json(list(map(str, args)), report=OUT / report)


def normalize(text):
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text)).lower()


def main(*, final_name="杭州-一城山水千年生长.mp4", manifest_name="render-manifest.json", expected_frames=4100, expected_cues=35, audio_times=(6, 25, 60, 78, 104, 120, 140, 153, 163)):
    final = OUT / final_name
    timeline = json.loads((OUT / "timeline.json").read_text())
    manifest = json.loads((OUT / manifest_name).read_text())
    stats = json.loads((FILM / "data/stats.json").read_text())
    assert hashlib.sha256((FILM / "data/model.json").read_bytes()).hexdigest() == stats["model_sha256"]
    probe = run(["probe", final, "--json"], "verified-final-probe.json")
    v, a = probe["video"], probe["audio"]
    assert v["nb_frames"] == manifest["frames"] == timeline["frames"] == expected_frames
    assert (v["width"], v["height"], v["fps"], v["pix_fmt"], v["color_range"]) == (1920, 1080, 24, "yuv420p", "tv")
    assert a["channels"] == 2 and a["sample_rate"] == 48000
    assert len(probe["chapters"]) == len(timeline["scenes"]) == 12
    assert len(timeline["cues"]) == expected_cues

    # Every caption is read back from a real encoded frame at its midpoint.
    args = ["look", final, "--width", "1920", "--no-timecode", "-o", OUT / "caption-frame.png", "--overwrite", "--json-brief"]
    for c in timeline["cues"]:
        args += ["--at", f"{(c['start'] + c['end']) / 2:.3f}"]
    result = run(args, "caption-frame-extraction.json")
    files = result["outputs"]
    assert len(files) == len(timeline["cues"])
    ocr_source = FILM / "tools/ocr_captions.swift"
    ocr_sha = hashlib.sha256(ocr_source.read_bytes()).hexdigest()
    binary = OUT / f"ocr-captions-{ocr_sha[:16]}"
    if not binary.exists():
        subprocess.run(["swiftc", str(ocr_source), "-o", str(binary)], check=True)
    r = subprocess.run([str(binary), *files], capture_output=True, text=True, check=True)
    (OUT / "caption-ocr-raw.json").write_text(r.stdout)
    ocr = json.loads(r.stdout)
    checks = []
    for cue, result in zip(timeline["cues"], ocr, strict=True):
        # Match the authored Chinese line independently of punctuation. The
        # English line may be returned as a second OCR observation.
        observed = "".join(result["text"])
        ok = normalize(cue["text"]) in normalize(observed)
        checks.append({"expected": cue["text"], "observed": result["text"], "frame": result["file"], "match": ok})
    (OUT / "caption-ocr-verification.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2))

    # An independent extraction checks that encoded audio still follows the
    # exact PCM mix timeline. Compare short waveform windows, not ASR words.
    # Bind extracted-audio and OCR executable caches to actual source bytes.
    final_sha = hashlib.sha256(final.read_bytes()).hexdigest()
    extracted = OUT / f"final-decoded-audio-{final_sha[:16]}.wav"
    if not extracted.exists():
        run(["audio", final, "-o", extracted, "--json-brief"], "decoded-audio-report.json")
    def pcm(p):
        with wave.open(str(p), "rb") as r:
            assert r.getframerate() == 48000 and r.getsampwidth() == 2
            return np.frombuffer(r.readframes(r.getnframes()), dtype="<i2").reshape(-1, r.getnchannels()).mean(axis=1).astype(np.float32)
    reference, actual = pcm(OUT / "mix.wav"), pcm(extracted)
    windows = []
    for t in audio_times:
        start = int(t * 48000)
        ref = reference[start:start + 48000:6]
        got = actual[start - 2400:start + 50400:6]
        scores = correlate(got, ref, mode="valid", method="fft")
        index = int(np.argmax(scores))
        aligned = got[index:index + len(ref)]
        offset = (index * 6 - 2400) / 48000
        corr = float(np.corrcoef(ref, aligned)[0, 1])
        windows.append({"at_seconds": t, "offset_seconds": offset, "correlation": corr})
    all_match = all(c["match"] for c in checks)
    audio_ok = all(abs(w["offset_seconds"]) <= 1 / 24 and w["correlation"] > .90 for w in windows)
    report = {
        "schema": "hangzhou-film-delivery-v1",
        "file": str(final), "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
        "frame_manifest_matches": True, "video_frames": v["nb_frames"], "video_duration": v["duration"],
        "container_duration": probe["duration"], "size_bytes": final.stat().st_size,
        "resolution": [1920, 1080], "fps": 24, "pixel_format": v["pix_fmt"], "color_range": v["color_range"],
        "audio": {"codec": a["codec"], "channels": a["channels"], "sample_rate": a["sample_rate"], "waveform_windows": windows, "timing_passed": audio_ok},
        "captions": {"method": timeline["caption_method"], "cues": expected_cues, "ocr_sample_per_cue": True, "ocr_matches": sum(c["match"] for c in checks), "all_sampled_captions_match": all_match},
        "subtitle_sync": {"passed": None, "reason": "Per-utterance PCM file intervals and encoded-frame OCR sampling; not the Qwen/sync.py acoustic gate"},
        "visual_generation": {"renderer": "Three.js / WebGL / Canvas", "generative_image_model_calls": 0, "generative_video_model_calls": 0},
        "data": stats,
        "limitations": ["Modern massing model with historical location/light overlays, not reconstructed ancient buildings", "CMAB heights are estimated except explicit OSM height replacements", "OCR samples one actual encoded frame per cue; it is not an every-frame subtitle audit", "No human listening review recorded"],
        "passed": bool(all_match and audio_ok)
    }
    (OUT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise ValueError("Caption OCR or actual audio alignment requires inspection; see verification.json")
    print(json.dumps({"caption_matches": report["captions"]["ocr_matches"], "audio_timing_passed": audio_ok, "sha256": report["sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    OUT = output_directory(protect_delivery=False)
    main()
