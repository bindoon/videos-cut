from __future__ import annotations

import hashlib
import re
from fractions import Fraction
from pathlib import Path

from .media import duration, probe, run, write_json
from .speech import write_srt
from .transcription import transcribe as recognize


def merge_intervals(
    intervals: list[tuple[float, float]], total: float
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for start, end in sorted((max(0, a), min(total, b)) for a, b in intervals if b > a):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def keep_intervals(
    removed: list[tuple[float, float]], total: float
) -> list[tuple[float, float]]:
    result, cursor = [], 0.0
    for start, end in merge_intervals(removed, total):
        if start > cursor:
            result.append((cursor, start))
        cursor = end
    if cursor < total:
        result.append((cursor, total))
    return result


def map_time(time: float, kept: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(time, end) - start) for start, end in kept)


def silence_intervals(
    path: Path, minimum: float = 0.55, margin: float = 0.12, threshold: int = -35
) -> list[tuple[float, float]]:
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={threshold}dB:d={minimum}",
            "-f",
            "null",
            "-",
        ]
    )
    total, intervals, start = duration(path), [], None
    for match in re.finditer(r"silence_(start|end): ([\d.]+)", result.stderr):
        if match[1] == "start":
            start = float(match[2])
        elif start is not None:
            end = float(match[2])
            if end - start > 2 * margin:
                intervals.append((start + margin, end - margin))
            start = None
    if start is not None and total - start > 2 * margin:
        intervals.append((start + margin, total - margin))
    return intervals


def transcribe(
    path: Path, output: Path, model: str = "base", language: str = "zh"
) -> dict:
    # Editing policy stays here; the standalone recognizer also accepts no-speech results.
    result = recognize(path, output, model, language)
    if not result["words"]:
        raise RuntimeError(
            "ASR returned no timed words; cannot safely cut or subtitle this recording"
        )
    blocks = keep_intervals(
        silence_intervals(path, minimum=0.55, margin=0.12), duration(path)
    )
    uncovered = []
    recognized = merge_intervals(
        [(w["start"], w["end"]) for w in result["words"]], duration(path)
    )
    for start, end in blocks:
        if end - start < 0.6:
            continue
        covered = sum(max(0, min(end, b) - max(start, a)) for a, b in recognized)
        # Only reject a completely unrecognized passage. A coverage ratio
        # incorrectly rejects short fillers separated by natural pauses.
        if covered <= 0:
            uncovered.append({"start": start, "end": end})
    result["coverage_check"] = {"uncovered_passages": uncovered}
    write_json(output, result)
    if uncovered:
        raise RuntimeError(
            f"ASR missed {len(uncovered)} audible passage(s). Use a larger --model or review the recording; see {output}"
        )
    return result


def normalize(text: str) -> str:
    text = text.translate(str.maketrans({"個": "个", "說": "说"}))
    return "".join(c.lower() for c in text if c.isalnum())


def filler_intervals(words: list[dict], fillers: list[str]) -> list[dict]:
    # Match complete timestamped tokens (or sequences of them), never a substring
    # such as 'um' inside 'summer', nor half of a coarse Chinese word timestamp.
    candidates = []
    for i, word in enumerate(words):
        for filler in fillers:
            target, combined = normalize(filler), ""
            if not target:
                continue
            for j in range(i, min(len(words), i + len(target) + 1)):
                if j > i and words[j]["start"] - words[j - 1]["end"] > 0.4:
                    break
                combined += normalize(words[j]["text"])
                if combined == target:
                    candidates.append(
                        {
                            "start": word["start"],
                            "end": words[j]["end"],
                            "reason": "filler",
                            "text": filler,
                        }
                    )
                    break
                if not target.startswith(combined):
                    break
    return candidates


def words_to_cues(words: list[dict], limit: int = 16) -> list[dict]:
    cues, current = [], None
    for word in words:
        text = word["text"].strip()
        if not text:
            continue
        if current and (
            len(current["text"]) + len(text) > limit
            or word["start"] - current["end"] > 0.5
        ):
            cues.append(current)
            current = None
        if current is None:
            current = {"start": word["start"], "end": word["end"], "text": text}
        else:
            current["text"] += (" " if text.isascii() else "") + text
            current["end"] = word["end"]
    if current:
        cues.append(current)
    return cues


def clean_video(
    source: Path,
    output: Path,
    *,
    transcript: dict | None = None,
    model="base",
    language="zh",
    fillers: list[str] | None = None,
    minimum=0.55,
    margin=0.12,
    breath_gate=False,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    total = duration(source)
    if transcript is None:
        transcript = transcribe(source, output / "transcript.json", model, language)
    else:
        if transcript.get("source_sha256"):
            with source.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != transcript["source_sha256"]:
                raise ValueError("Transcript belongs to a different recording")
        if not transcript.get("words") or any(
            not 0 <= w["start"] <= w["end"] <= total + 0.25 for w in transcript["words"]
        ):
            raise ValueError(
                "Transcript must contain words with valid source timestamps"
            )
        write_json(output / "transcript.json", transcript)
    candidates = [
        {"start": a, "end": b, "reason": "silence"}
        for a, b in silence_intervals(source, minimum, margin)
    ]
    candidates += filler_intervals(
        transcript["words"],
        fillers if fillers is not None else ["嗯", "呃", "um", "uh"],
    )
    stream = next(s for s in probe(source)["streams"] if s["codec_type"] == "video")
    fps = float(Fraction(stream.get("avg_frame_rate", "24/1")))
    # Quantize audio and video to the same frame boundaries; otherwise many
    # short cuts can accumulate one video frame of A/V drift per splice.
    removed = merge_intervals(
        [
            (round(c["start"] * fps) / fps, round(c["end"] * fps) / fps)
            for c in candidates
        ],
        total,
    )
    kept = keep_intervals(removed, total)
    if not kept:
        raise ValueError("The edit would remove the entire recording")
    graph, concat = [], []
    for i, (start, end) in enumerate(kept):
        graph += [
            f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]",
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={max(0, end - start - 0.008)}:d=0.008[a{i}]",
        ]
        concat += [f"[v{i}][a{i}]"]
    graph.append("".join(concat) + f"concat=n={len(kept)}:v=1:a=1[vout][aconcat]")
    audio_filter = "highpass=f=65,afftdn=nf=-30"
    if breath_gate:
        audio_filter += ",agate=threshold=0.006:ratio=2:attack=10:release=120"
    graph.append(f"[aconcat]{audio_filter}[aout]")
    target = output / "cleaned.mp4"
    print(
        f"精剪: {total:.2f}s → {sum(b - a for a, b in kept):.2f}s · {len(removed)} 个删除区间",
        flush=True,
    )
    script = output / "cut.ffscript"
    script.write_text(";".join(graph))
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-filter_complex_threads",
            "2",
            "-i",
            str(source),
            "-filter_complex_script",
            str(script),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-threads",
            "4",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    adjusted = []
    for word in transcript["words"]:
        if any(
            c["reason"] == "filler"
            and word["start"] >= c["start"] - 0.025
            and word["end"] <= c["end"] + 0.025
            for c in candidates
        ):
            continue
        surviving = [
            (max(word["start"], a), min(word["end"], b))
            for a, b in kept
            if min(word["end"], b) > max(word["start"], a)
        ]
        if not surviving:
            continue
        start, end = map_time(surviving[0][0], kept), map_time(surviving[-1][1], kept)
        if end > start:
            adjusted.append({**word, "start": start, "end": end})
    write_srt(words_to_cues(adjusted), output / "cleaned.srt")
    write_json(
        output / "edit-plan.json",
        {
            "source": str(source.resolve()),
            "input_seconds": total,
            "output_seconds": duration(target),
            "removed_seconds": sum(b - a for a, b in removed),
            "candidates": candidates,
            "removed": removed,
            "kept": kept,
            "breath_gate": breath_gate,
            "asr_engine": transcript.get("engine"),
            "adjusted_words": adjusted,
        },
    )
    return target
