"""Independent local ASR with bounded PCM windows and resumable, content-checked chunks."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import json
import math
import re
import time
from pathlib import Path

from .media import decode_audio, probe, run
from .speech import write_srt

SCHEMA = "local-asr-word-midpoint-v1"
SAMPLE_RATE = 16000
OUTPUTS = ("transcript.json", "transcript.txt", "transcript.srt")


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _atomic_json(path: Path, value):
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def _atomic_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


@contextlib.contextmanager
def _lock(path: Path):
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _load_model(path: Path):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Speech recognition requires: uv sync --extra asr (retain --extra download if needed)"
        ) from exc
    return WhisperModel(str(path), device="cpu", compute_type="int8", cpu_threads=4)


def _model_path(model: str) -> Path:
    for candidate in (Path(model).expanduser(), Path("assets/models") / model):
        if (candidate / "model.bin").is_file() and (
            candidate / "config.json"
        ).is_file():
            return candidate.resolve()
    try:
        from faster_whisper.utils import download_model
    except ImportError as exc:
        raise RuntimeError("Speech recognition requires: uv sync --extra asr") from exc
    print(f"准备 Whisper 模型: {model}", flush=True)
    return Path(download_model(model, cache_dir="assets/models")).resolve()


def chunk_plan(total: float, seconds: float, overlap: float) -> list[dict]:
    if (
        not all(math.isfinite(v) for v in (total, seconds, overlap))
        or total <= 0
        or seconds <= 0
        or not 0 <= overlap < seconds / 2
    ):
        raise ValueError(
            "Positive chunk duration required; overlap must be nonnegative and less than half a chunk"
        )
    plan = [
        {
            "start": round(i * seconds, 6),
            "end": round(min(total, (i + 1) * seconds), 6),
            "decode_start": round(max(0, i * seconds - overlap), 6),
            "decode_end": round(min(total, (i + 1) * seconds + overlap), 6),
        }
        for i in range(math.ceil(total / seconds))
    ]
    # ffprobe can expose sub-microsecond tails that round to an empty PCM window.
    return [
        p for p in plan if p["end"] > p["start"] and p["decode_end"] > p["decode_start"]
    ]


def _prepare(
    path: Path,
    model: str,
    language: str,
    chunk_seconds: float,
    overlap_seconds: float,
    cache: Path,
) -> dict:
    chunk_seconds, overlap_seconds = float(chunk_seconds), float(overlap_seconds)
    chunk_plan(1, chunk_seconds, overlap_seconds)
    language = language.lower()
    if language != "auto" and not re.fullmatch(r"[a-z]{2,3}", language):
        raise ValueError(
            "Use --language auto or a Whisper language code such as zh or en"
        )
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"Local media file not found: {path}; download URLs separately"
        )
    source_stat = (path.stat().st_size, path.stat().st_mtime_ns)
    source_hash = _file_hash(path)
    info = probe(path)
    if not any(s["codec_type"] == "audio" for s in info.get("streams", [])):
        raise ValueError("Input has no audio stream")
    total = float(info["format"]["duration"])
    plan = chunk_plan(total, chunk_seconds, overlap_seconds)
    model_path = _model_path(str(model))
    files = {
        p.name: _file_hash(p)
        for p in sorted(model_path.iterdir())
        if p.is_file() and p.suffix in {".bin", ".json", ".txt"}
    }
    versions = {}
    for name in ("faster-whisper", "ctranslate2"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unavailable"
    options = {
        "language": language,
        "chunk_seconds": chunk_seconds,
        "overlap_seconds": overlap_seconds,
        "sample_rate": SAMPLE_RATE,
        "beam_size": 5,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 400, "speech_pad_ms": 120},
        "condition_on_previous_text": False,
        "word_timestamps": True,
        "initial_prompt": "以下是普通话的简体中文逐字转写，保留口语词。"
        if language == "zh"
        else None,
    }
    identity = {
        "schema": SCHEMA,
        "source_sha256": source_hash,
        "model_files": files,
        "backend_versions": versions,
        "ffmpeg": run(["ffmpeg", "-version"]).stdout.splitlines()[0],
        "options": options,
    }
    key = _digest(identity)
    return {
        "path": path,
        "source_stat": source_stat,
        "total": total,
        "model": str(model),
        "model_path": model_path,
        "identity": identity,
        "options": options,
        "plan": plan,
        "key": key,
        "folder": cache.expanduser().resolve() / key,
    }


def _unchanged(request: dict):
    stat = request["path"].stat()
    if (stat.st_size, stat.st_mtime_ns) != request["source_stat"]:
        raise RuntimeError(
            "Source changed during transcription; rerun against a stable local file"
        )


def _interval(start, end, lower, upper):
    start, end = float(start), float(end)
    if not math.isfinite(start) or not math.isfinite(end) or end < start:
        raise ValueError("ASR returned invalid timestamps")
    return round(max(lower, min(start, upper)), 6), round(
        max(lower, min(end, upper)), 6
    )


def _chunk_result(segments, info, plan: dict, samples: int) -> dict:
    result = []
    offset, upper = plan["decode_start"], plan["decode_end"]
    for segment in segments:
        start, end = _interval(
            offset + segment.start, offset + segment.end, offset, upper
        )
        words = []
        for word in segment.words or []:
            a, b = _interval(offset + word.start, offset + word.end, offset, upper)
            if b > a and word.word.strip():
                words.append(
                    {
                        "start": a,
                        "end": b,
                        "text": word.word,
                        "probability": float(word.probability),
                    }
                )
        if end > start and segment.text.strip():
            result.append(
                {"start": start, "end": end, "text": segment.text, "words": words}
            )
    return {
        "plan": plan,
        "language": info.language if result else None,
        "language_probability": info.language_probability if result else None,
        "segments": result,
        "decoded_samples": samples,
    }


def _read_chunk(path: Path, request: dict, plan: dict) -> dict | None:
    try:
        envelope = json.loads(path.read_text())
        payload = envelope["payload"]
        if (
            envelope["key"] != request["key"]
            or envelope["checksum"] != _digest(payload)
            or payload["plan"] != plan
        ):
            return None
        for segment in payload["segments"]:
            for row in [segment, *segment["words"]]:
                if (
                    not plan["decode_start"]
                    <= row["start"]
                    < row["end"]
                    <= plan["decode_end"]
                ):
                    return None
        return payload
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _owns(row: dict, plan: dict, total: float) -> bool:
    midpoint = (row["start"] + row["end"]) / 2
    return (
        plan["start"] <= midpoint < plan["end"]
        or plan["end"] == total
        and midpoint == total
    )


def merge_chunks(chunks: list[dict], total: float) -> tuple[list[dict], list[dict]]:
    """Assign each estimated word by its midpoint; repeated words are never text-deduplicated."""
    segments, words = [], []
    for chunk in chunks:
        plan = chunk["plan"]

        for segment in chunk["segments"]:
            owned = [w for w in segment["words"] if _owns(w, plan, total)]
            if owned:
                words.extend(owned)
                segments.append(
                    {
                        "start": min(w["start"] for w in owned),
                        "end": max(w["end"] for w in owned),
                        "text": "".join(w["text"] for w in owned),
                    }
                )
            elif not segment["words"] and _owns(segment, plan, total):
                segments.append({k: segment[k] for k in ("start", "end", "text")})
    return sorted(segments, key=lambda s: (s["start"], s["end"])), sorted(
        words, key=lambda w: (w["start"], w["end"])
    )


def _recognize(request: dict, force: bool) -> dict:
    started = time.monotonic()
    folder = request["folder"]
    options = request["options"]
    model, chunks, hits = None, [], 0
    decoded_counts = []
    with _lock(folder / ".lock"):
        for index, plan in enumerate(request["plan"]):
            _unchanged(request)
            target = folder / f"chunk-{index:05}.json"
            payload = None if force else _read_chunk(target, request, plan)
            if payload is not None:
                hits += 1
                print(
                    f"转录 {index + 1}/{len(request['plan'])}: 复用已校验缓存",
                    flush=True,
                )
            else:
                print(
                    f"转录 {index + 1}/{len(request['plan'])}: {plan['start']:.1f}–{plan['end']:.1f} 秒",
                    flush=True,
                )
                audio = decode_audio(
                    request["path"],
                    start=plan["decode_start"],
                    seconds=plan["decode_end"] - plan["decode_start"],
                )
                if model is None:
                    model = _load_model(request["model_path"])
                raw, info = model.transcribe(
                    audio,
                    language=None
                    if options["language"] == "auto"
                    else options["language"],
                    word_timestamps=True,
                    vad_filter=True,
                    vad_parameters=options["vad_parameters"],
                    condition_on_previous_text=False,
                    initial_prompt=options["initial_prompt"],
                    beam_size=5,
                )
                payload = _chunk_result(raw, info, plan, len(audio))
                decoded_counts.append(len(audio))
                del audio
                _unchanged(request)
                _atomic_json(
                    target,
                    {
                        "key": request["key"],
                        "checksum": _digest(payload),
                        "payload": payload,
                    },
                )
            chunks.append(payload)
        _unchanged(request)
        _atomic_json(
            folder / "manifest.json",
            {
                "schema": SCHEMA,
                "key": request["key"],
                "identity": request["identity"],
                "chunk_count": len(chunks),
                "complete": True,
            },
        )
    segments, words = merge_chunks(chunks, request["total"])
    languages = {}
    for chunk in chunks:
        if chunk["language"]:
            languages[chunk["language"]] = languages.get(chunk["language"], 0) + len(
                chunk["segments"]
            )
    return {
        "schema": SCHEMA,
        "engine": "faster-whisper",
        "origin": "local_asr",
        "model": request["model"],
        "model_identity": request["identity"]["model_files"],
        "backend_versions": request["identity"]["backend_versions"],
        "language": max(languages, key=languages.get) if languages else None,
        "languages": languages,
        "requested_language": options["language"],
        "source_sha256": request["identity"]["source_sha256"],
        "source_path": str(request["path"]),
        "source_duration": request["total"],
        "status": "transcribed" if segments else "no_speech",
        "segments": segments,
        "words": words,
        "vad_filter": True,
        "options": options,
        "runtime": {
            "cache_key": request["key"],
            "chunk_count": len(chunks),
            "chunks_reused": hits,
            "chunks_inferred": len(chunks) - hits,
            "model_loaded": model is not None,
            "max_decoded_samples": max(decoded_counts, default=0),
            "max_chunk_samples": max(c["decoded_samples"] for c in chunks),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        },
    }


def transcribe(
    path: Path,
    output: Path,
    model: str = "base",
    language: str = "auto",
    *,
    chunk_seconds: float = 600,
    overlap_seconds: float = 1,
    cache: Path = Path("assets/cache/transcripts"),
    force: bool = False,
) -> dict:
    if path.expanduser().resolve() == output.expanduser().resolve():
        raise ValueError("Transcript output must not overwrite the source media")
    request = _prepare(path, model, language, chunk_seconds, overlap_seconds, cache)
    result = _recognize(request, force)
    _atomic_json(output, result)
    return result


def transcribe_to_directory(
    path: Path,
    output: Path,
    model: str = "base",
    language: str = "auto",
    *,
    chunk_seconds: float = 600,
    overlap_seconds: float = 1,
    cache: Path = Path("assets/cache/transcripts"),
    force: bool = False,
    overwrite: bool = False,
) -> dict:
    request = _prepare(path, model, language, chunk_seconds, overlap_seconds, cache)
    if any(
        (output / name).resolve() == request["path"]
        for name in (*OUTPUTS, "transcription-report.json")
    ):
        raise ValueError(
            "Output must not overwrite the source media; choose a different directory"
        )
    with _lock(output / ".transcription.lock"):
        report_path = output / "transcription-report.json"
        if not overwrite and (
            report_path.exists() or any((output / name).exists() for name in OUTPUTS)
        ):
            try:
                old = json.loads(report_path.read_text())
                valid = old["cache_key"] == request["key"] and all(
                    _file_hash(output / name) == old["outputs"][name]
                    for name in OUTPUTS
                )
            except (OSError, ValueError, KeyError, TypeError):
                valid = False
            if not valid:
                raise ValueError(
                    "Output contains edited or different transcription results; choose a new directory or pass --overwrite"
                )
        result = _recognize(request, force)
        _atomic_json(output / "transcript.json", result)
        _atomic_text(
            output / "transcript.txt",
            "\n".join(s["text"].strip() for s in result["segments"])
            + ("\n" if result["segments"] else ""),
        )
        temporary = output / "transcript.srt.tmp"
        write_srt(result["segments"], temporary)
        temporary.replace(output / "transcript.srt")
        _atomic_json(
            report_path,
            {
                "schema": SCHEMA,
                "status": result["status"],
                "source": str(request["path"]),
                "source_sha256": result["source_sha256"],
                "requested_language": result["requested_language"],
                "language": result["language"],
                **result["runtime"],
                "outputs": {name: _file_hash(output / name) for name in OUTPUTS},
                "note": "Local ASR estimates; no semantic accuracy or forced-alignment guarantee. No source-media download, editing, or LLM stage was run.",
            },
        )
    return result


def validate_timed_words(transcript: dict, source: Path):
    """Consumers may require timed words even when standalone no-speech export is valid."""
    if (
        transcript.get("source_sha256")
        and _file_hash(source) != transcript["source_sha256"]
    ):
        raise ValueError("Transcript belongs to a different recording")
    total = float(probe(source)["format"]["duration"])
    if not transcript.get("words") or any(
        not 0 <= w["start"] <= w["end"] <= total + 0.25 for w in transcript["words"]
    ):
        raise ValueError("Transcript must contain words with valid source timestamps")
