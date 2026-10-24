from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import urllib.request
import wave
from pathlib import Path

from .media import run, write_json


async def edge_speak(text: str, target: Path, voice: str, rate: str) -> None:
    import edge_tts

    proxy = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or urllib.request.getproxies().get("https")
    )
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, proxy=proxy, connect_timeout=15, receive_timeout=30
    )
    await asyncio.wait_for(communicate.save(str(target)), timeout=50)


def synthesize_line(
    text: str, folder: Path, provider: str, voice: str, rate: str
) -> Path:
    key = hashlib.sha256(f"{provider}|{voice}|{rate}|{text}".encode()).hexdigest()[:16]
    wav = folder / f"{key}.wav"
    if wav.exists():
        try:
            with wave.open(str(wav), "rb") as cached:
                if cached.getnframes() > 0:
                    return wav
        except (wave.Error, EOFError):
            pass
    source = folder / (f"{key}.mp3" if provider == "edge" else f"{key}.aiff")
    print(f"配音 [{provider}]: {text}", flush=True)
    if provider == "edge":
        asyncio.run(edge_speak(text, source, voice, rate))
    elif provider == "macos":
        if not shutil.which("say"):
            raise RuntimeError("macos voice requires the macOS say command")
        run(["say", "-v", "Tingting", "-r", "185", "-o", str(source), text], timeout=60)
    else:
        raise ValueError(f"Unknown speech provider: {provider}")
    temporary = wav.with_suffix(".wav.part")
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(temporary),
        ]
    )
    temporary.replace(wav)
    return wav


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def write_srt(cues: list[dict], path: Path) -> None:
    path.write_text(
        "\n\n".join(
            f"{i}\n{srt_time(cue['start'])} --> {srt_time(cue['end'])}\n{cue['text']}"
            for i, cue in enumerate(cues, 1)
        )
        + "\n",
        encoding="utf-8",
    )


def read_srt(path: Path) -> list[dict]:
    """The renderer consumes the serialized SRT, not a second private timeline."""

    def seconds(value):
        hours, minutes, rest = value.split(":")
        secs, millis = rest.split(",")
        return int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000

    result = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            raise ValueError("Invalid generated SRT")
        start, end = lines[1].split(" --> ")
        cue = {
            "text": "\n".join(lines[2:]),
            "start": seconds(start),
            "end": seconds(end),
        }
        if cue["end"] <= cue["start"]:
            raise ValueError("Invalid SRT interval")
        result.append(cue)
    return result


def build_narration(
    config: dict,
    output: Path,
    provider: str,
    prepared_speech: dict[str, str] | None = None,
    *,
    align_to_speech: bool = False,
    word_alignment: dict | None = None,
    alignment_python: Path = Path(".venv-align/bin/python"),
    alignment_model: Path = Path("assets/models/Qwen3-ForcedAligner-0.6B"),
) -> tuple[list[dict], list[dict], Path]:
    folder = output / "speech"
    folder.mkdir(parents=True, exist_ok=True)
    scenes, cues = [], []
    source_paths = {}
    if align_to_speech:
        from .captions import create_caption_plan

        plan = create_caption_plan(config)
        write_json(output / "caption-plan.json", plan)
    narration = output / "narration.wav"
    samples = 0
    with wave.open(str(narration), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(48000)
        for scene in config["scenes"]:
            start = samples / 48000
            for text in scene["lines"]:
                path = (
                    Path(prepared_speech[text])
                    if prepared_speech is not None
                    else synthesize_line(
                        text,
                        folder,
                        provider,
                        config.get("voice", "zh-CN-XiaoxiaoNeural"),
                        config.get("rate", "+0%"),
                    )
                )
                with wave.open(str(path), "rb") as reader:
                    if (
                        reader.getnchannels(),
                        reader.getsampwidth(),
                        reader.getframerate(),
                    ) != (1, 2, 48000):
                        raise ValueError(
                            f"Narration segment must be mono 48kHz PCM16: {path}"
                        )
                    count = reader.getnframes()
                    raw = reader.readframes(count)
                source_paths[text] = path
                cues.append(
                    {
                        "start": samples / 48000,
                        "end": (samples + count) / 48000,
                        "text": text,
                    }
                )
                writer.writeframes(raw)
                samples += count
                gap = round(0.12 * 48000)
                writer.writeframes(b"\0\0" * gap)
                samples += gap
            scenes.append(
                {**scene, "start": start, "duration": samples / 48000 - start}
            )
        writer.writeframes(b"\0\0" * 24000)
    scenes[-1]["duration"] += 0.5
    alignment_method = "per-utterance PCM sample counts"
    if align_to_speech:
        from .captions import (
            SCHEMA,
            align_pcm_cues,
            align_script_cues,
            collect_alignment,
            needs_word_alignment,
            validate_caption_plan,
        )

        if not needs_word_alignment(plan):
            cues, alignment_report = align_pcm_cues(cues, source_paths, plan)
        else:
            if word_alignment is None:
                word_alignment = collect_alignment(
                    source_paths, output, alignment_python, alignment_model
                )
            if word_alignment.get("schema") != SCHEMA:
                raise ValueError(
                    "Regenerate Qwen alignment for the fixed subtitle plan"
                )
            write_json(output / "qwen-alignment.json", word_alignment)
            cues, alignment_report = align_script_cues(
                cues,
                source_paths,
                word_alignment,
                plan,
                narration_end=samples / 48000 + 0.5,
            )
        write_json(output / "caption-alignment.json", alignment_report)
        alignment_method = alignment_report["method"]
    write_srt(cues, output / "captions.srt")
    cues = read_srt(output / "captions.srt")
    if align_to_speech:
        validate_caption_plan(cues, plan)
    write_json(
        output / "captions.json",
        {
            "provider": provider,
            "alignment": alignment_method,
            "cues": cues,
        },
    )
    return scenes, cues, narration
