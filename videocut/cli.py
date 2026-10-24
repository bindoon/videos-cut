from __future__ import annotations

import argparse
import json
import sys
import time
import wave
from pathlib import Path

from .assets import download_materials
from .media import duration, require_tools, run, write_json
from .speech import build_narration, synthesize_line, write_srt


def existing_audio(
    config: dict, audio: Path, output: Path, model: str, transcript: dict | None = None
) -> tuple:
    from .cleaning import transcribe, words_to_cues

    if transcript is None:
        transcript = transcribe(audio, output / "transcript.json", model)
    cues = words_to_cues(transcript["words"])
    # Boundaries follow actual subtitle utterances, not estimated speech speed.
    count = min(len(config["scenes"]), len(cues))
    total = duration(audio)
    scenes = []
    for i in range(count):
        a, b = i * len(cues) // count, (i + 1) * len(cues) // count
        start = 0 if i == 0 else cues[a]["start"]
        end = total if i == count - 1 else cues[b]["start"]
        scenes.append(
            {
                **config["scenes"][i],
                "lines": [c["text"] for c in cues[a:b]],
                "start": start,
                "duration": end - start,
            }
        )
    minimum_scene = max(1.0, float(config.get("transition_seconds", 0.35)) + 0.1)
    while len(scenes) > 1:
        short = next(
            (i for i, s in enumerate(scenes) if s["duration"] < minimum_scene), None
        )
        if short is None:
            break
        if short == 0:
            scenes[0]["lines"] += scenes[1]["lines"]
            scenes[0]["duration"] += scenes[1]["duration"]
            scenes.pop(1)
        else:
            scenes[short - 1]["lines"] += scenes[short]["lines"]
            scenes[short - 1]["duration"] += scenes[short]["duration"]
            scenes.pop(short)
    write_srt(cues, output / "captions.srt")
    write_json(
        output / "captions.json",
        {
            "provider": "existing_audio",
            "alignment": "faster-whisper word timestamps",
            "cues": cues,
        },
    )
    return scenes, cues, audio


def render(args) -> None:
    from .render import compose, inspect_output, render_backgrounds

    started = time.monotonic()
    if (args.output / "final.mp4").exists():
        raise ValueError(
            "Output already contains final.mp4; use a new directory to preserve it"
        )
    if args.transcript and not (args.audio or args.command == "mix"):
        raise ValueError("--transcript requires --audio or a mix input video")
    if args.caption_alignment and (args.audio or args.command == "mix"):
        raise ValueError("--caption-alignment applies to generated narration")
    if args.caption_alignment and args.caption_mode == "file":
        raise ValueError("--caption-alignment conflicts with --caption-mode file")
    if args.speech_manifest and (args.audio or args.command == "mix"):
        raise ValueError("--speech-manifest applies only to generated narration")
    if args.speech_manifest and args.tts not in {"clone", "indextts"}:
        raise ValueError("--speech-manifest requires --tts clone or indextts")
    speech_captions = not (args.audio or args.command == "mix") and (
        args.caption_mode == "speech"
        or args.caption_alignment is not None
        or (args.caption_mode is None and args.tts == "indextts")
    )
    config = json.loads(args.config.read_text())
    if not config.get("scenes") or any(not s.get("lines") for s in config["scenes"]):
        raise ValueError("Every scene must provide non-empty lines")
    from .captions import create_caption_plan, needs_word_alignment

    if speech_captions and needs_word_alignment(create_caption_plan(config)):
        # Fail before expensive synthesis when an alignment prerequisite is absent.
        if args.caption_alignment:
            provided = json.loads(args.caption_alignment.read_text())
            if provided.get("schema") != "qwen-forced-v1":
                raise ValueError(
                    "Regenerate Qwen alignment for fixed subtitle lines; see docs/subtitle-sync.md"
                )
        elif (
            not args.alignment_python.is_file()
            or not (args.alignment_model / "model.safetensors").is_file()
        ):
            raise ValueError(
                "Prepare the Qwen aligner environment and model before TTS; see docs/subtitle-sync.md"
            )
    if args.width:
        config["width"], config["height"] = (
            args.width,
            round(args.width * 16 / 9 / 2) * 2,
        )
    if config["width"] % 2 or config["height"] % 2:
        raise ValueError("H.264 width and height must be even")
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "project.json", config)
    if speech_captions:
        from .captions import create_caption_plan

        write_json(args.output / "caption-plan.json", create_caption_plan(config))
    materials = download_materials(args.materials, Path("assets/cache"))
    transcript = json.loads(args.transcript.read_text()) if args.transcript else None
    cleaning_report = None
    clone_metadata = None
    if args.command == "mix":
        from .cleaning import clean_video

        cleaned = clean_video(
            args.input,
            args.output / "cleaning",
            model=args.model,
            transcript=transcript,
            fillers=args.fillers,
            breath_gate=args.breath_gate,
        )
        cleaning_report = json.loads(
            (args.output / "cleaning/edit-plan.json").read_text()
        )
        transcript = {
            "engine": "faster-whisper; timestamps rebased after cuts",
            "words": cleaning_report["adjusted_words"],
        }
        args.audio = cleaned
        materials.append(
            {
                "id": "original-recording",
                "kind": "video",
                "filename": cleaned.name,
                "path": str(cleaned.resolve()),
                "tags": ["原始口播"],
                "credit": "User-provided input recording",
            }
        )
    write_json(args.output / "sources.json", materials)
    if args.audio:
        scenes, cues, narration = existing_audio(
            config, args.audio, args.output, args.model, transcript
        )
        if args.command == "mix":
            for i, scene in enumerate(scenes):
                if i % 2 == 0:
                    scene.update(
                        {
                            "kind": "video",
                            "material_id": "original-recording",
                            "source_start": scene["start"],
                        }
                    )
    else:
        prepared_speech = None
        if args.speech_manifest:
            import hashlib

            cloned = json.loads(args.speech_manifest.read_text())
            expected_provider = {"indextts": "IndexTTS-2.5", "clone": "F5-TTS-MLX"}.get(
                args.tts
            )
            if cloned.get("provider") != expected_provider:
                raise ValueError("Speech manifest provider does not match --tts")
            prepared_speech = {}
            for record in cloned["utterances"]:
                path = Path(record["path"])
                with path.open("rb") as stream:
                    checksum = hashlib.file_digest(stream, "sha256").hexdigest()
                if checksum != record["sha256"]:
                    raise ValueError(f"Cached speech checksum mismatch: {path}")
                prepared_speech[record["text"]] = str(path)
            clone_metadata = {k: v for k, v in cloned.items() if k != "utterances"}
        if args.tts == "indextts" and prepared_speech is None:
            if not args.reference_audio:
                raise ValueError("--tts indextts requires --reference-audio")
            request = {
                "config": config,
                "reference_audio": str(args.reference_audio.resolve()),
                "model_path": str(args.index_model.resolve()),
                "upstream_path": str(args.index_upstream.resolve()),
                "device": args.index_device,
                "output": str((args.output / "speech").resolve()),
            }
            request_path = args.output / "index-request.json"
            write_json(request_path, request)
            print("使用本地 IndexTTS-2.5 生成参考音色旁白", flush=True)
            result = run(
                [
                    str(args.index_python),
                    "-u",
                    "scripts/index_narration.py",
                    "--request",
                    str(request_path),
                ],
                timeout=1800,
            )
            print(result.stdout, flush=True)
            cloned = json.loads(
                (args.output / "speech/index-manifest.json").read_text()
            )
            clone_metadata = {
                key: cloned[key]
                for key in (
                    "provider",
                    "reference_audio",
                    "reference_sha256",
                    "model_sha256",
                    "model_revision",
                    "upstream_revision",
                    "cache_key",
                )
            }
            prepared_speech = {r["text"]: r["path"] for r in cloned["utterances"]}
        if args.tts == "clone" and prepared_speech is None:
            if not args.reference_audio:
                raise ValueError("--tts clone requires --reference-audio")
            reference_text = args.reference_text
            if not reference_text:
                from .cleaning import transcribe

                reference_transcript = transcribe(
                    args.reference_audio,
                    args.output / "reference-transcript.json",
                    args.model,
                )
                reference_text = "".join(
                    s["text"] for s in reference_transcript["segments"]
                )
            request = {
                "config": config,
                "reference_audio": str(args.reference_audio.resolve()),
                "reference_text": reference_text,
                "model_path": str(args.clone_model.resolve()),
                "vocoder_path": str(args.clone_vocoder.resolve()),
                "output": str((args.output / "speech").resolve()),
            }
            request_path = args.output / "clone-request.json"
            write_json(request_path, request)
            print("本地克隆参考音色并生成新旁白", flush=True)
            result = run(
                [
                    str(args.voice_python),
                    "-u",
                    "scripts/clone_narration.py",
                    "--request",
                    str(request_path),
                ],
                timeout=1800,
            )
            print(result.stdout, flush=True)
            cloned = json.loads(
                (args.output / "speech/clone-manifest.json").read_text()
            )
            clone_metadata = {
                key: cloned[key]
                for key in (
                    "provider",
                    "reference_audio",
                    "reference_sha256",
                    "model_sha256",
                    "cache_key",
                )
            }
            prepared_speech = {r["text"]: r["path"] for r in cloned["utterances"]}
        scenes, cues, narration = build_narration(
            config,
            args.output,
            args.tts,
            prepared_speech,
            align_to_speech=speech_captions,
            word_alignment=json.loads(args.caption_alignment.read_text())
            if args.caption_alignment
            else None,
            alignment_python=args.alignment_python,
            alignment_model=args.alignment_model,
        )
    if args.background:
        from .media import probe

        background = args.background
        stream = next(
            s for s in probe(background)["streams"] if s["codec_type"] == "video"
        )
        if (stream["width"], stream["height"]) != (config["width"], config["height"]):
            raise ValueError("Cached background dimensions differ from config")
        if abs(duration(background) - duration(narration)) > 0.1:
            raise ValueError("Cached background duration differs from narration")
        timeline = scenes
        write_json(
            args.output / "timeline.json",
            {"scenes": scenes, "reused_background": str(background.resolve())},
        )
    else:
        background, timeline = render_backgrounds(
            config, scenes, materials, args.output
        )
    final = compose(
        config,
        background,
        scenes,
        cues,
        narration,
        materials,
        args.output,
        target_name="candidate.mp4",
    )
    report = inspect_output(final, args.output, duration(narration))
    alignment_path = args.output / "caption-alignment.json"
    if alignment_path.exists():
        from .sync import verify_subtitle_sync

        sync = verify_subtitle_sync(
            final,
            config,
            cues,
            json.loads(alignment_path.read_text()),
            narration,
            args.output,
        )
        report["subtitle_sync"] = {
            "passed": sync["passed"],
            "checked_captions": len(cues),
        }
    else:
        report["subtitle_sync"] = {
            "passed": None,
            "reason": "This mode has no forced alignment; sync is unverified",
        }
    final = final.replace(args.output / "final.mp4")
    report.update(
        {
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "speech_provider": "existing_audio" if args.audio else args.tts,
            "paid_api_calls": 0,
            "cost_note": "No paid API invoked. Local compute, bandwidth and storage are not priced here.",
            "scene_count": len(timeline),
            "caption_count": len(cues),
            "sticker_count": sum(bool(s.get("sticker")) for s in scenes),
            "transitions": [s.get("transition", "fade") for s in scenes[:-1]],
            "loudness_target_lufs": -16,
            "transcript_source": "provided" if args.transcript else "generated",
            "voice_cloning": clone_metadata,
            "cleaning": None
            if cleaning_report is None
            else {
                k: cleaning_report[k]
                for k in ("input_seconds", "output_seconds", "removed_seconds")
            },
        }
    )
    write_json(args.output / "verification.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"成片: {final.resolve()}")


def raw_sample(args) -> None:
    folder = args.output
    folder.mkdir(parents=True, exist_ok=True)
    speech = folder / "speech"
    speech.mkdir(exist_ok=True)
    lines = [
        "今天，给自己留一杯咖啡的时间。",
        "那个，就是说。",
        "从新鲜的咖啡豆开始。",
        "嗯，那个。",
        "慢慢来，也是一种生活的节奏。",
    ]
    total = 0
    truth = []
    with wave.open(str(folder / "raw.wav"), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(48000)
        for i, text in enumerate(lines):
            audio = synthesize_line(
                text, speech, args.tts, "zh-CN-XiaoxiaoNeural", "-5%"
            )
            with wave.open(str(audio), "rb") as reader:
                frames = reader.getnframes()
                writer.writeframes(reader.readframes(frames))
            truth.append(
                {
                    "start": total / 48000,
                    "end": (total + frames) / 48000,
                    "text": text,
                    "type": "filler" if i in {1, 3} else "content",
                }
            )
            total += frames
            silence = round((1.6 if i < len(lines) - 1 else 0.4) * 48000)
            writer.writeframes(b"\0\0" * silence)
            total += silence
    write_json(
        folder / "ground-truth.json",
        {
            "synthetic_fixture": True,
            "note": "Reference for evaluating the cut only; never provided to ASR/cutter",
            "utterances": truth,
        },
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-stream_loop",
            "-1",
            "-i",
            str(args.video),
            "-i",
            str(folder / "raw.wav"),
            "-t",
            str(total / 48000),
            "-vf",
            "scale=480:854:force_original_aspect_ratio=increase,crop=480:854,setsar=1,fps=24",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-threads",
            "2",
            str(folder / "raw.mp4"),
        ]
    )
    print(f"可控精剪测试素材（合成旁白＋下载画面）: {(folder / 'raw.mp4').resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="素材混剪：配音、字幕、转场、贴纸和口播精剪"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "render", "mix"):
        command = sub.add_parser(name)
        command.add_argument(
            "--config", type=Path, default=Path("examples/coffee.json")
        )
        command.add_argument(
            "--materials", type=Path, default=Path("examples/materials.json")
        )
        command.add_argument("--output", type=Path, default=Path("outputs/coffee"))
        command.add_argument(
            "--tts", choices=["edge", "macos", "clone", "indextts"], default="edge"
        )
        command.add_argument("--reference-audio", type=Path)
        command.add_argument("--reference-text")
        command.add_argument(
            "--caption-mode",
            choices=["speech", "file"],
            help="Generated captions: speech phrases (IndexTTS default) or whole audio files",
        )
        command.add_argument(
            "--caption-alignment",
            type=Path,
            help="Reuse SHA-256 checked Qwen forced alignment; subtitle lines stay fixed",
        )
        command.add_argument(
            "--alignment-python", type=Path, default=Path(".venv-align/bin/python")
        )
        command.add_argument(
            "--alignment-model",
            type=Path,
            default=Path("assets/models/Qwen3-ForcedAligner-0.6B"),
        )
        command.add_argument(
            "--speech-manifest",
            type=Path,
            help="Reuse checksum-verified cloned WAVs without TTS inference",
        )
        command.add_argument(
            "--background",
            type=Path,
            help="Reuse an explicitly supplied rendered background",
        )
        command.add_argument(
            "--clone-model", type=Path, default=Path("assets/models/F5-TTS-MLX")
        )
        command.add_argument(
            "--clone-vocoder", type=Path, default=Path("assets/models/vocos-mel-24khz")
        )
        command.add_argument(
            "--voice-python", type=Path, default=Path(".venv-voice/bin/python")
        )
        command.add_argument(
            "--index-python", type=Path, default=Path(".venv-index/bin/python")
        )
        command.add_argument(
            "--index-model", type=Path, default=Path("assets/models/IndexTTS-2.5")
        )
        command.add_argument(
            "--index-upstream", type=Path, default=Path("upstream/index-tts-reference")
        )
        command.add_argument(
            "--index-device", choices=["mps", "cpu", "cuda"], default="mps"
        )
        command.add_argument(
            "--audio",
            type=Path,
            help="Use an existing narration recording and real ASR subtitles",
        )
        command.add_argument("--model", default="base")
        command.add_argument(
            "--transcript",
            type=Path,
            help="Reuse/correct timed words JSON for the same recording",
        )
        command.add_argument("--width", type=int)
        if name == "mix":
            command.add_argument("input", type=Path)
            command.add_argument(
                "--fillers", nargs="+", default=["嗯", "呃", "um", "uh"]
            )
            command.add_argument("--breath-gate", action="store_true")
    command = sub.add_parser("download")
    command.add_argument(
        "--materials", type=Path, default=Path("examples/materials.json")
    )
    command = sub.add_parser("raw-sample")
    command.add_argument(
        "--video", type=Path, default=Path("assets/cache/espresso.mp4")
    )
    command.add_argument("--output", type=Path, default=Path("outputs/raw-sample"))
    command.add_argument("--tts", choices=["edge", "macos"], default="edge")
    command = sub.add_parser("cut")
    command.add_argument("input", type=Path)
    command.add_argument("--output", type=Path, default=Path("outputs/cleaned"))
    command.add_argument("--model", default="base")
    command.add_argument("--language", default="zh")
    command.add_argument("--fillers", nargs="+", default=["嗯", "呃", "um", "uh"])
    command.add_argument("--minimum-silence", type=float, default=0.55)
    command.add_argument("--margin", type=float, default=0.12)
    command.add_argument("--breath-gate", action="store_true")
    command = sub.add_parser(
        "rough-cut", help="Invoke upstream Auto-Editor for silence-only first pass"
    )
    command.add_argument("input", type=Path)
    command.add_argument("--output", type=Path, default=Path("outputs/auto-editor.mp4"))
    args = parser.parse_args()
    require_tools()
    if args.command in {"demo", "render", "mix"}:
        render(args)
    elif args.command == "download":
        download_materials(args.materials, Path("assets/cache"))
    elif args.command == "raw-sample":
        raw_sample(args)
    elif args.command == "cut":
        from .cleaning import clean_video

        print(
            clean_video(
                args.input,
                args.output,
                model=args.model,
                language=args.language,
                fillers=args.fillers,
                minimum=args.minimum_silence,
                margin=args.margin,
                breath_gate=args.breath_gate,
            )
        )
    elif args.command == "rough-cut":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = run(
            [
                sys.executable,
                "-m",
                "auto_editor",
                str(args.input),
                "--margin",
                "0.12s",
                "--no-open",
                "--output",
                str(args.output),
            ]
        )
        print(result.stdout[-3000:])
        write_json(
            args.output.with_suffix(".json"),
            {
                "engine": "upstream auto-editor",
                "input_seconds": duration(args.input),
                "output_seconds": duration(args.output),
            },
        )


if __name__ == "__main__":
    main()
