"""Real FFmpeg orchestration checks. The model double does NOT establish ASR accuracy."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from videocut.media import decode_audio, run


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "speech.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=10",
            str(path),
        ]
    )
    return path


@pytest.fixture
def model_double(tmp_path, monkeypatch):
    from videocut import transcription

    model = tmp_path / "fixture-model"
    model.mkdir()
    (model / "model.bin").write_bytes(b"test model identity, not real weights")
    (model / "config.json").write_text("{}")
    state = {"loads": 0, "calls": [], "fail_on": None, "silent": False}

    class Model:
        def transcribe(self, audio, **kwargs):
            state["calls"].append({"samples": len(audio), **kwargs})
            if state["fail_on"] == len(state["calls"]):
                raise RuntimeError("fixture model interrupted")
            words = (
                []
                if state["silent"]
                else [
                    SimpleNamespace(
                        start=0.25, end=0.75, word=" fixture", probability=0.9
                    )
                ]
            )
            segments = (
                []
                if state["silent"]
                else [
                    SimpleNamespace(start=0.25, end=0.75, text=" fixture", words=words)
                ]
            )
            return iter(segments), SimpleNamespace(
                language=kwargs.get("language") or "en", language_probability=0.99
            )

    def load(_):
        state["loads"] += 1
        return Model()

    monkeypatch.setattr(transcription, "_load_model", load)
    return str(model), state


def test_window_decode_is_bounded_and_original_decode_remains_usable(recording):
    whole = decode_audio(recording)
    window = decode_audio(recording, start=3, seconds=2)
    assert abs(len(whole) / 16000 - 10) < 0.01
    assert abs(len(window) / 16000 - 2) < 0.01


def test_standalone_exports_global_timestamps_and_cache(
    recording, model_double, tmp_path
):
    from videocut.transcription import transcribe_to_directory

    model, state = model_double
    output = tmp_path / "out"
    result = transcribe_to_directory(
        recording,
        output,
        model=model,
        language="auto",
        chunk_seconds=4,
        overlap_seconds=0.5,
        cache=tmp_path / "cache",
    )
    # A midpoint exactly on a core boundary belongs to the following chunk.
    assert [round(w["start"], 2) for w in result["words"]] == [0.25, 3.75, 7.75]
    assert all(c["samples"] <= 5 * 16000 for c in state["calls"])
    assert all(
        c["language"] is None and c["initial_prompt"] is None for c in state["calls"]
    )
    assert (
        output / "transcript.txt"
    ).read_text().strip() == "fixture\nfixture\nfixture"
    assert "00:00:07,750" in (output / "transcript.srt").read_text()
    before = len(state["calls"])
    transcribe_to_directory(
        recording,
        tmp_path / "cached",
        model=model,
        chunk_seconds=4,
        overlap_seconds=0.5,
        cache=tmp_path / "cache",
    )
    report = json.loads((tmp_path / "cached/transcription-report.json").read_text())
    assert report["chunks_reused"] == 3 and report["chunks_inferred"] == 0
    assert report["max_decoded_samples"] == 0
    assert len(state["calls"]) == before and state["loads"] == 1


def test_overlap_word_ownership_keeps_real_repetitions():
    from videocut.transcription import merge_chunks

    chunks = [
        {
            "plan": {"start": 0.0, "end": 4.0, "decode_start": 0.0, "decode_end": 4.5},
            "segments": [
                {
                    "start": 3.5,
                    "end": 4.5,
                    "text": " go go",
                    "words": [
                        {"start": 3.5, "end": 3.9, "text": " go", "probability": 1.0},
                        {"start": 4.0, "end": 4.3, "text": " go", "probability": 1.0},
                    ],
                }
            ],
        },
        {
            "plan": {"start": 4.0, "end": 8.0, "decode_start": 3.5, "decode_end": 8.0},
            "segments": [
                {
                    "start": 3.5,
                    "end": 4.5,
                    "text": " go go",
                    "words": [
                        {"start": 3.5, "end": 3.9, "text": " go", "probability": 1.0},
                        {"start": 4.0, "end": 4.3, "text": " go", "probability": 1.0},
                    ],
                }
            ],
        },
    ]
    segments, words = merge_chunks(chunks, 8)
    assert len(words) == 2
    assert [w["start"] for w in words] == [3.5, 4.0]
    assert "".join(s["text"] for s in segments).split() == ["go", "go"]


def test_failed_chunk_resume_and_corrupted_chunk_repair(
    recording, model_double, tmp_path
):
    from videocut.transcription import transcribe

    model, state = model_double
    state["fail_on"] = 2
    kwargs = {
        "model": model,
        "chunk_seconds": 4,
        "overlap_seconds": 0.5,
        "cache": tmp_path / "cache",
    }
    with pytest.raises(RuntimeError, match="fixture model interrupted"):
        transcribe(recording, tmp_path / "first.json", **kwargs)
    assert not (tmp_path / "first.json").exists()
    state["fail_on"] = None
    result = transcribe(recording, tmp_path / "second.json", **kwargs)
    assert result["runtime"]["chunks_reused"] == 1
    chunks = sorted((tmp_path / "cache").rglob("chunk-*.json"))
    broken = json.loads(chunks[0].read_text())
    broken["payload"]["segments"][0]["text"] = "tampered"
    broken["payload"]["segments"][0]["words"][0]["text"] = "tampered"
    chunks[0].write_text(json.dumps(broken))
    repaired = transcribe(recording, tmp_path / "third.json", **kwargs)
    assert repaired["runtime"]["chunks_inferred"] == 1
    assert "tampered" not in str(repaired["segments"])


def test_language_and_model_changes_invalidate_cache(recording, model_double, tmp_path):
    from videocut.transcription import transcribe

    model, state = model_double
    cache = tmp_path / "cache"
    first = transcribe(recording, tmp_path / "auto.json", model=model, cache=cache)
    same = transcribe(
        recording,
        tmp_path / "same.json",
        model=model,
        cache=cache,
        chunk_seconds=600.0,
        overlap_seconds=1.0,
    )
    assert first["runtime"]["cache_key"] == same["runtime"]["cache_key"]
    assert same["runtime"]["chunks_reused"] == 1
    chinese = transcribe(
        recording, tmp_path / "zh.json", model=model, language="zh", cache=cache
    )
    assert first["runtime"]["cache_key"] != chinese["runtime"]["cache_key"]
    assert state["calls"][-1]["initial_prompt"] is not None
    (Path(model) / "model.bin").write_bytes(b"replacement model weights")
    changed = transcribe(recording, tmp_path / "changed.json", model=model, cache=cache)
    assert first["runtime"]["cache_key"] != changed["runtime"]["cache_key"]


def test_standalone_silence_is_explicit_but_editing_still_rejects(
    recording, model_double, tmp_path, monkeypatch
):
    from videocut import cleaning
    from videocut.transcription import transcribe_to_directory

    model, state = model_double
    state["silent"] = True
    result = transcribe_to_directory(
        recording, tmp_path / "silent", model=model, cache=tmp_path / "cache"
    )
    assert result["status"] == "no_speech" and not result["words"]
    assert not (tmp_path / "silent/transcript.srt").read_text().strip()
    monkeypatch.setattr(cleaning, "recognize", lambda *a, **kw: result)
    with pytest.raises(RuntimeError, match="no timed words"):
        cleaning.transcribe(recording, tmp_path / "editing.json", model)


def test_export_protects_corrected_text_and_other_sources(
    recording, model_double, tmp_path
):
    from videocut.transcription import transcribe_to_directory

    model, _ = model_double
    output = tmp_path / "out"
    kwargs = {"model": model, "cache": tmp_path / "cache"}
    transcribe_to_directory(recording, output, **kwargs)
    (output / "transcript.txt").write_text("human correction")
    with pytest.raises(ValueError, match="overwrite"):
        transcribe_to_directory(recording, output, **kwargs)
    assert (output / "transcript.txt").read_text() == "human correction"
    transcribe_to_directory(recording, output, overwrite=True, **kwargs)
    with pytest.raises(ValueError, match="overwrite"):
        transcribe_to_directory(recording, output, language="zh", **kwargs)


def test_invalid_windows_and_no_audio_fail_before_inference(
    recording, model_double, tmp_path
):
    from videocut.transcription import transcribe

    model, state = model_double
    with pytest.raises(ValueError):
        transcribe(recording, tmp_path / "invalid.json", model=model, chunk_seconds=0)
    video = tmp_path / "silent-video.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=160x284:d=1",
            "-an",
            str(video),
        ]
    )
    with pytest.raises(ValueError, match="audio"):
        transcribe(video, tmp_path / "no-audio.json", model=model)
    assert state["loads"] == 0


def test_overwrite_never_replaces_source_media(recording, model_double, tmp_path):
    from videocut.transcription import transcribe_to_directory

    model, state = model_double
    output = tmp_path / "out"
    output.mkdir()
    source = output / "transcript.json"
    original = recording.read_bytes()
    source.write_bytes(original)
    with pytest.raises(ValueError, match="source media"):
        transcribe_to_directory(source, output, model=model, overwrite=True)
    assert source.read_bytes() == original
    assert state["loads"] == 0


def test_existing_audio_rejects_transcript_from_another_source(recording, tmp_path):
    from videocut.cli import existing_audio

    transcript = {
        "source_sha256": "another-file",
        "words": [{"start": 0, "end": 1, "text": "wrong source"}],
    }
    with pytest.raises(ValueError, match="different recording"):
        existing_audio(
            {"scenes": [{"lines": ["placeholder"]}]},
            recording,
            tmp_path,
            "base",
            transcript,
        )


def test_cut_cli_consumes_saved_transcript_without_loading_a_model(recording, tmp_path):
    import subprocess
    import sys

    media = tmp_path / "input.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=160x284:r=24:d=2",
            "-i",
            str(recording),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(media),
        ]
    )
    transcript = tmp_path / "provided.json"
    transcript.write_text(
        json.dumps(
            {
                "engine": "provided timestamp fixture, not ASR",
                "source_sha256": hashlib.sha256(media.read_bytes()).hexdigest(),
                "words": [
                    {"start": 0.1, "end": 0.8, "text": "first"},
                    {"start": 1.1, "end": 1.8, "text": "second"},
                ],
            }
        )
    )
    output = tmp_path / "cut"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "videocut",
            "cut",
            str(media),
            "--transcript",
            str(transcript),
            "--model",
            str(tmp_path / "missing-model"),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    assert (output / "cleaned.mp4").exists()
    saved = json.loads((output / "transcript.json").read_text())
    assert saved["engine"] == "provided timestamp fixture, not ASR"
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(output / "cleaned.mp4"),
            "-f",
            "null",
            "-",
        ]
    )
    invalid_command = [*proc.args[:-1], str(tmp_path / "invalid-cut")]
    for value in ({}, None, [], {"words": []}):
        transcript.write_text(json.dumps(value))
        invalid = subprocess.run(
            invalid_command, check=False, capture_output=True, text=True, timeout=20
        )
        assert invalid.returncode == 1
        assert "Transcript must contain words" in invalid.stderr
