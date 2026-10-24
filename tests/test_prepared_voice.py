import json
import wave

import pytest

from videocut.speech import build_narration


def write_pcm(path, rate=48000):
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x34\x12" * 4800)


@pytest.mark.parametrize("provider", ["clone", "indextts"])
def test_cloned_voice_uses_prepared_audio_without_builtin_fallback(
    tmp_path, monkeypatch, provider
):
    source = tmp_path / "cloned.wav"
    write_pcm(source)

    def forbidden(*args, **kwargs):
        raise AssertionError("Reference voice must not fall back to a built-in voice")

    monkeypatch.setattr("videocut.speech.synthesize_line", forbidden)
    output = tmp_path / "new-run"
    output.mkdir()
    scenes, cues, audio = build_narration(
        {"scenes": [{"lines": ["你好。"]}]}, output, provider, {"你好。": str(source)}
    )
    with wave.open(str(audio), "rb") as reader:
        assert reader.readframes(4800) == b"\x34\x12" * 4800
    assert cues[0]["end"] == 0.1
    assert scenes[0]["duration"] == 0.72
    assert json.loads((output / "captions.json").read_text())["provider"] == provider


def test_wrong_reference_audio_rate_cannot_silently_change_voice_pitch(tmp_path):
    source = tmp_path / "wrong-rate.wav"
    write_pcm(source, 44100)
    output = tmp_path / "new-run"
    output.mkdir()
    with pytest.raises(ValueError, match="mono 48kHz PCM16"):
        build_narration(
            {"scenes": [{"lines": ["你好。"]}]},
            output,
            "clone",
            {"你好。": str(source)},
        )
