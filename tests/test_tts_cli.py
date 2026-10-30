import json
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from videocut import cli


def command_args(monkeypatch, command, *options):
    captured = []
    monkeypatch.setattr(cli, "require_tools", lambda: None)
    monkeypatch.setattr(cli, "render", captured.append)
    monkeypatch.setattr(cli, "raw_sample", captured.append)
    arguments = ["videocut", command]
    if command == "mix":
        arguments.append("input.mp4")
    monkeypatch.setattr(sys, "argv", arguments + list(options))
    cli.main()
    return captured[0]


@pytest.mark.parametrize("command", ["demo", "render", "mix", "raw-sample"])
def test_all_synthesis_commands_default_to_indextts25(monkeypatch, command):
    args = command_args(monkeypatch, command)
    assert args.tts == "indextts"
    assert args.index_model == Path("assets/models/IndexTTS-2.5")
    assert args.index_python == Path(".venv-index/bin/python")


@pytest.mark.parametrize("provider", ["edge", "macos"])
def test_builtin_voices_remain_explicit_choices(monkeypatch, provider):
    assert command_args(monkeypatch, "render", "--tts", provider).tts == provider


@pytest.mark.parametrize(
    "options",
    [
        ["--tts", "clone"],
        ["--reference-text", "参考逐字稿"],
        ["--clone-model", "model"],
        ["--clone-vocoder", "vocoder"],
        ["--voice-python", "python"],
    ],
)
def test_removed_f5_options_are_rejected(monkeypatch, options):
    monkeypatch.setattr(sys, "argv", ["videocut", "render", *options])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_default_render_requires_reference_before_downloading(tmp_path, monkeypatch):
    render = cli.render
    args = command_args(monkeypatch, "render", "--output", str(tmp_path / "new"))

    def forbidden(*args, **kwargs):
        raise AssertionError("Missing reference must fail before material downloads")

    monkeypatch.setattr(cli, "download_materials", forbidden)
    with pytest.raises(ValueError, match="requires --reference-audio"):
        render(args)
    assert not args.output.exists()


def test_default_render_dispatches_index_and_keeps_speech_captions(tmp_path, monkeypatch):
    render = cli.render
    config = tmp_path / "project.json"
    config.write_text(json.dumps({
        "width": 48, "height": 48,
        "caption_switch": "audio_clip", "scenes": [{"lines": ["你好。"]}],
    }))
    args = command_args(
        monkeypatch, "render", "--config", str(config),
        "--reference-audio", str(tmp_path / "reference.wav"),
        "--output", str(tmp_path / "new"),
    )
    monkeypatch.setattr(cli, "download_materials", lambda *a: [])
    requested = []

    def generate(config, args):
        requested.append(args.tts)
        return {
            "provider": "IndexTTS-2.5", "reference_audio": "reference.wav",
            "reference_sha256": "ref", "model_sha256": {}, "model_revision": "rev",
            "upstream_revision": "rev", "cache_key": "key",
            "utterances": [{"text": "你好。", "path": "prepared.wav"}],
        }

    class NarrationReached(Exception):
        pass

    def build(config, output, provider, prepared_speech, **kwargs):
        assert provider == "indextts"
        assert prepared_speech == {"你好。": "prepared.wav"}
        assert kwargs["align_to_speech"] is True
        raise NarrationReached

    monkeypatch.setattr(cli, "generate_index_speech", generate)
    monkeypatch.setattr(cli, "build_narration", build)
    with pytest.raises(NarrationReached):
        render(args)
    assert requested == ["indextts"]


def test_raw_sample_uses_index25_request_and_generated_pcm(tmp_path, monkeypatch):
    raw_sample = cli.raw_sample
    args = command_args(
        monkeypatch, "raw-sample", "--reference-audio", str(tmp_path / "reference.wav"),
        "--output", str(tmp_path / "sample"),
    )
    requests = []

    def run(command, **kwargs):
        if command[0] == "ffmpeg":
            return SimpleNamespace(stdout="")
        assert command[:3] == [".venv-index/bin/python", "-u", "scripts/index_narration.py"]
        request = json.loads(Path(command[-1]).read_text())
        assert request["model_path"] == str(Path("assets/models/IndexTTS-2.5").resolve())
        assert request["reference_audio"] == str(args.reference_audio)
        requests.append(request)
        records = []
        for i, text in enumerate(request["config"]["scenes"][0]["lines"]):
            source = args.output / "speech" / f"{i}.wav"
            with wave.open(str(source), "wb") as writer:
                writer.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
                writer.writeframes(b"\x34\x12" * 4800)
            records.append({"text": text, "path": str(source)})
        (args.output / "speech/index-manifest.json").write_text(json.dumps({"utterances": records}))
        return SimpleNamespace(stdout="Generated IndexTTS-2.5")

    def forbidden(*args, **kwargs):
        raise AssertionError("IndexTTS must use prepared PCM without a built-in fallback")

    monkeypatch.setattr(cli, "run", run)
    monkeypatch.setattr(cli, "synthesize_line", forbidden)
    raw_sample(args)
    assert len(requests) == 1
    with wave.open(str(args.output / "raw.wav"), "rb") as reader:
        assert reader.readframes(4800) == b"\x34\x12" * 4800
    truth = json.loads((args.output / "ground-truth.json").read_text())
    assert len(truth["utterances"]) == 5
    assert truth["utterances"][0]["end"] == 0.1


def test_f5_manifest_cannot_be_reused_as_default_index_speech(tmp_path, monkeypatch):
    render = cli.render
    config = tmp_path / "project.json"
    config.write_text(json.dumps({"width": 48, "height": 48, "scenes": [{"lines": ["你好。"]}]}))
    manifest = tmp_path / "f5.json"
    manifest.write_text(json.dumps({"provider": "F5-TTS-MLX", "utterances": []}))
    args = command_args(
        monkeypatch, "render", "--config", str(config), "--caption-mode", "file",
        "--speech-manifest", str(manifest), "--output", str(tmp_path / "new"),
    )
    monkeypatch.setattr(cli, "download_materials", lambda *a: [])
    with pytest.raises(ValueError, match="provider does not match"):
        render(args)
