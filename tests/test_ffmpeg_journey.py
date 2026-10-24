import json
from pathlib import Path

from videocut.cleaning import clean_video
from videocut.media import decode_audio, duration, probe, run


def test_real_ffmpeg_cut_preserves_av_sync_and_rebases_subtitles(tmp_path: Path):
    source = tmp_path / "source.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x284:rate=24:duration=4",
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=if(between(t\\,1\\,2)\\,0\\,0.15*sin(2*PI*440*t)):s=48000:d=4",
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
    words = [
        {"text": "hello", "start": 0.1, "end": 1.2},
        {"text": "um", "start": 2.4, "end": 2.8},
        {"text": "world", "start": 3, "end": 3.6},
    ]
    waveform = decode_audio(source)
    assert waveform.dtype.name == "float32"
    assert abs(len(waveform) / 16000 - 4) < 0.05
    assert 0.1 < float(abs(waveform).max()) < 0.3
    target = clean_video(
        source,
        tmp_path / "edited",
        transcript={"engine": "test timestamp fixture, not ASR", "words": words},
        fillers=["um"],
    )
    plan = json.loads((tmp_path / "edited/edit-plan.json").read_text())
    assert 1.0 < plan["removed_seconds"] < 1.3
    assert abs(duration(target) - (4 - plan["removed_seconds"])) < 0.1
    assert [w["text"] for w in plan["adjusted_words"]] == ["hello", "world"]
    world = plan["adjusted_words"][1]
    assert abs(world["start"] - (3 - plan["removed_seconds"])) < 0.05
    streams = probe(target)["streams"]
    lengths = [float(s["duration"]) for s in streams if "duration" in s]
    assert max(lengths) - min(lengths) < 0.1
    run(["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"])
