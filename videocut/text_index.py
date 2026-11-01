"""Normalize subtitle tracks into a search index, never forced-alignment records."""
from __future__ import annotations

import html
import json
import re
from itertools import pairwise
from pathlib import Path

from .image_ops import atomic_json, number, sha256, video_info


def timestamp(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    try:
        values = [float(p) for p in parts]
        if not all(0 <= v < 60 for v in values[-2:]) or any(v < 0 for v in values):
            raise ValueError
        return sum(v * 60 ** i for i, v in enumerate(reversed(values)))
    except ValueError:
        raise ValueError(f"Invalid subtitle timestamp: {value}") from None


def parse_track(text: str) -> list[dict]:
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").lstrip("\ufeff")):
        lines = block.splitlines()
        if not lines or lines[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        for i, line in enumerate(lines):
            if "-->" not in line:
                continue
            left, right = line.split("-->", 1)
            start, end = timestamp(left.strip()), timestamp(right.strip().split()[0])
            content = html.unescape(re.sub(r"<[^>]+>", "", " ".join(lines[i + 1:])))
            content = re.sub(r"\s+", " ", content).strip()
            if end <= start:
                raise ValueError("Subtitle end must be after start")
            if content:
                cues.append({"start": start, "end": end, "text": content,
                             "source_cues": [len(cues)]})
            break
    if not cues:
        raise ValueError("No usable SRT/VTT cues")
    if any(b["start"] < a["start"] for a, b in pairwise(cues)):
        raise ValueError("Subtitle cues must be chronological")
    return cues


def deduplicate(cues: list[dict]) -> list[dict]:
    """Merge overlapping rolling repeats; keep repetitions after a real gap."""
    result = []
    for cue in cues:
        cue = {**cue, "source_cues": list(cue["source_cues"])}
        if result and cue["start"] <= result[-1]["end"] + 0.12:
            previous = result[-1]
            a, b = previous["text"], cue["text"]
            if a == b or b.startswith(a) or a.startswith(b):
                previous["text"] = b if len(b) > len(a) else a
                previous["end"] = max(previous["end"], cue["end"])
                previous["source_cues"].extend(cue["source_cues"])
                continue
        result.append(cue)
    return result


def build_index(track: Path, source: Path, output: Path, *, kind: str = "platform",
                generation: str = "unspecified", language: str = "unspecified") -> dict:
    if kind not in {"platform", "asr", "user"}:
        raise ValueError("kind must be platform, asr or user")
    if generation not in {"unspecified", "automatic", "human"}:
        raise ValueError("Invalid generation provenance")
    track = track.expanduser().resolve(strict=True)
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Index output already exists: {output}")
    info = video_info(source)
    track_checksum = sha256(track)
    raw = track.read_text(encoding="utf-8-sig")
    if track.suffix.lower() == ".json":
        data = json.loads(raw)
        if kind != "asr" or data.get("source_sha256") != info["sha256"]:
            raise ValueError("ASR JSON must match source_sha256 and use --kind asr")
        cues = [{"start": s["start"], "end": s["end"], "text": s["text"],
                 "source_cues": [i]} for i, s in enumerate(data.get("segments", []))]
    else:
        cues = parse_track(raw)
    for i, cue in enumerate(cues):
        number(cue["start"], "cue start", 0, info["duration"])
        number(cue["end"], "cue end", cue["start"], info["duration"] + 0.25)
        if cue["end"] <= cue["start"] or not str(cue["text"]).strip():
            raise ValueError("Index cue requires positive duration and text")
        if i and cue["start"] < cues[i - 1]["start"]:
            raise ValueError("Index cues must be chronological")
    normalized = deduplicate(cues)
    for cue in normalized:
        cue["candidate_time"] = min((cue["start"] + cue["end"]) / 2,
                                    info["duration"] - 1e-6)
    result = {"schema": "text-frame-index-v1", "source": info,
              "track": {"path": str(track), "sha256": track_checksum, "kind": kind,
                        "generation": generation, "language": language},
              "cues": normalized, "input_cues": len(cues),
              "timing": "subtitle/ASR estimates; candidate frames require visual review",
              "burned_in_subtitles": "unverified", "semantic_review": "pending"}
    output.parent.mkdir(parents=True, exist_ok=True)
    if sha256(track) != track_checksum or sha256(Path(info["path"])) != info["sha256"]:
        raise ValueError("Source or track changed during indexing")
    atomic_json(output, result)
    return result
