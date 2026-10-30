"""Generate authored Hangzhou narration through the existing speech provider.

Timings come from decoded PCM sample counts, then round-trip through SRT.
No ASR timestamps are presented as forced alignment records.
"""
from __future__ import annotations

from paths import output_directory

import concurrent.futures
import hashlib
import json
import pathlib
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from videocut.speech import synthesize_line, write_srt, read_srt

FILM = ROOT / "films/hangzhou"
OUT = None
DATA = FILM / "data"
RATE = 48000


def main():
    story = json.loads((FILM / "story.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(exist_ok=True)
    folder = OUT / "speech"
    folder.mkdir(exist_ok=True)
    lines = [l[0] for s in story["scenes"] for l in s["lines"]]

    def make(text):
        return text, synthesize_line(text, folder, "edge", story["voice"], story["rate"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        paths = dict(ex.map(make, lines))
    samples, cues, scenes, segments = 0, [], [], []
    with wave.open(str(OUT / "narration.wav"), "wb") as w:
        w.setparams((1, 2, RATE, 0, "NONE", "not compressed"))

        def silence(seconds):
            nonlocal samples
            n = round(seconds * RATE)
            w.writeframes(b"\0\0" * n)
            samples += n

        for si, s in enumerate(story["scenes"]):
            start = samples / RATE
            silence(2.0 if si == 0 else 0.65)
            for text, en in s["lines"]:
                p = paths[text]
                with wave.open(str(p), "rb") as r:
                    assert (r.getnchannels(), r.getsampwidth(), r.getframerate()) == (1, 2, RATE)
                    n = r.getnframes()
                    raw = r.readframes(n)
                t0 = samples / RATE
                w.writeframes(raw)
                samples += n
                cues.append({"start": t0, "end": samples / RATE, "text": text, "en": en, "scene": s["id"]})
                segments.append({"text": text, "path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "samples": n, "start_sample": round(t0 * RATE)})
                silence(0.28)
            silence(4.8 if si == len(story["scenes"]) - 1 else 0.8)
            scenes.append({**s, "start": start, "end": samples / RATE})
    write_srt(cues, OUT / "captions.srt")
    serialized = read_srt(OUT / "captions.srt")
    for cue, timing in zip(cues, serialized, strict=True):
        cue.update(timing)
    frames = round(samples / RATE * 24)
    timeline = {"title": story["title"], "subtitle": story["subtitle"], "fps": 24, "frames": frames, "duration": frames / 24,
                "voice": story["voice"], "provider": "edge", "caption_method": "per-utterance PCM sample counts; SRT readback", "scenes": scenes, "cues": cues}
    for path in [OUT / "timeline.json", DATA / "timeline.json"]:
        path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))
    (OUT / "speech-manifest.json").write_text(json.dumps({"provider": "edge", "voice": story["voice"], "rate": story["rate"], "sample_rate": RATE, "segments": segments}, ensure_ascii=False, indent=2))
    print("NARRATION", timeline["duration"], "seconds", len(cues), "cues", flush=True)


if __name__ == "__main__":
    OUT = output_directory(protect_delivery=True)
    main()
