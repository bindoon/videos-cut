"""Freeze subtitle lines first; locate those exact lines in the actual narration."""

from __future__ import annotations

import hashlib
import json
import math
import re
from itertools import pairwise
from pathlib import Path

from .media import run, write_json

SCHEMA = "qwen-forced-v1"
PHRASES = r"[^，。！？；、,.!?;]+[，。！？；、,.!?;]*"


def normalized(text):
    return "".join(c for c in text if c.isalnum())


def create_caption_plan(config):
    """A fixed display contract, created before speech synthesis/alignment."""
    overrides = config.get("subtitle_phrases", {})
    layout = config.get("caption_layout", "utterance")
    if layout not in {"utterance", "phrases"}:
        raise ValueError("caption_layout must be utterance or phrases")
    utterances = []
    texts = [text for scene in config["scenes"] for text in scene["lines"]]
    if set(overrides) - set(texts):
        raise ValueError(
            "subtitle_phrases contains an utterance absent from the script"
        )
    for i, text in enumerate(texts):
        default_parts = (
            [text]
            if layout == "utterance"
            else [m.group().strip() for m in re.finditer(PHRASES, text)]
        )
        parts = overrides.get(text, default_parts)
        if (
            not isinstance(parts, list)
            or not parts
            or any(not isinstance(p, str) or not normalized(p) for p in parts)
            or normalized("".join(parts)) != normalized(text)
        ):
            raise ValueError(
                f"Subtitle lines must cover the exact narration in order: {text}"
            )
        position, groups = 0, []
        for j, part in enumerate(parts):
            count = len(normalized(part))
            groups.append(
                {
                    "id": f"u{i:03}-c{j:02}",
                    "text": part,
                    "char_start": position,
                    "char_end": position + count,
                }
            )
            position += count
        utterances.append({"text": text, "groups": groups})
    lead = float(config.get("caption_lead_seconds", 0.20))
    if not math.isfinite(lead) or not 0 <= lead <= 0.25:
        raise ValueError("caption_lead_seconds must be between 0 and 0.25")
    whole_sentences = all(len(u["groups"]) == 1 for u in utterances)
    switch = config.get(
        "caption_switch", "previous_speech_end" if whole_sentences else "audio_clip"
    )
    if switch not in {"previous_speech_end", "audio_clip"}:
        raise ValueError("caption_switch must be previous_speech_end or audio_clip")
    if switch == "previous_speech_end" and not whole_sentences:
        raise ValueError(
            "previous_speech_end requires one complete caption per utterance"
        )
    return {
        "schema": "fixed-caption-plan-v1",
        "layout": layout,
        "switch": switch,
        "utterances": utterances,
        "first_caption": "utterance_audio_start",
        "lead_seconds": lead,
    }


def validate_caption_plan(cues, plan):
    expected = [g["text"] for u in plan["utterances"] for g in u["groups"]]
    if [c["text"] for c in cues] != expected:
        raise ValueError(
            "SRT lines differ from the fixed caption plan; merging, dropping or rewriting is forbidden"
        )


def needs_word_alignment(plan):
    return plan.get("switch") == "previous_speech_end" or any(
        len(u["groups"]) > 1 for u in plan["utterances"]
    )


def align_pcm_cues(cues, paths, plan):
    """One complete caption per WAV: times come only from PCM sample counts."""
    if needs_word_alignment(plan):
        raise ValueError("Split subtitles require word alignment")
    result, references, utterances = [], [], []
    for cue, planned in zip(cues, plan["utterances"], strict=True):
        if cue["text"] != planned["text"]:
            raise ValueError("Audio utterances differ from the fixed caption plan")
        with Path(paths[cue["text"]]).open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        text = planned["groups"][0]["text"]
        result.append({**cue, "text": text})
        references.append(
            {
                "id": planned["groups"][0]["id"],
                "text": text,
                "first_in_utterance": True,
                "utterance_start": cue["start"],
                "utterance_end": cue["end"],
                "audio_start": cue["start"],
                "audio_end": cue["end"],
                "end_basis": "audio_clip_end",
                "audio_sha256": checksum,
            }
        )
        utterances.append(
            {
                "text": cue["text"],
                "file_start": cue["start"],
                "file_end": cue["end"],
                "audio_sha256": checksum,
            }
        )
    validate_caption_plan(result, plan)
    return result, {
        "schema": "pcm-caption-v1",
        "method": "one fixed caption per PCM audio clip; no estimated word timing",
        "plan": plan,
        "references": references,
        "utterances": utterances,
    }


def collect_alignment(
    paths,
    output,
    python=Path(".venv-align/bin/python"),
    model=Path("assets/models/Qwen3-ForcedAligner-0.6B"),
):
    request, destination = (
        output / "alignment-request.json",
        output / "qwen-alignment.json",
    )
    write_json(
        request,
        {
            "model": str(model.resolve()),
            "output": str(destination.resolve()),
            "utterances": [
                {"expected": text, "path": str(Path(path).resolve())}
                for text, path in paths.items()
            ],
        },
    )
    if not (model / "model.safetensors").is_file():
        raise ValueError(
            "Missing Qwen forced alignment model; see docs/subtitle-sync.md"
        )
    result = run(
        [str(python), "-u", "scripts/align_qwen.py", "--request", str(request)],
        timeout=900,
    )
    print(result.stdout, flush=True)
    return json.loads(destination.read_text())


def align_script_cues(cues, paths, alignment, plan=None, *, narration_end=None):
    if alignment.get("schema") != SCHEMA:
        raise ValueError(
            "Expected Qwen forced alignment; old ASR/CTC timing must be regenerated"
        )
    if plan is None:
        plan = create_caption_plan({"scenes": [{"lines": [c["text"] for c in cues]}]})
    if [c["text"] for c in cues] != [u["text"] for u in plan["utterances"]]:
        raise ValueError("Audio utterances differ from the fixed caption plan")
    indexed = {r["expected"]: r for r in alignment["utterances"]}
    result, references, audit = [], [], []
    for cue, planned in zip(cues, plan["utterances"]):
        text, path = cue["text"], Path(paths[cue["text"]])
        record = indexed[text]
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != record["audio_sha256"]:
            raise ValueError(
                f"Subtitle timing belongs to a different audio file: {text}"
            )
        words, boundaries, position = record["words"], {}, 0
        if normalized("".join(w["text"] for w in words)) != normalized(text):
            raise ValueError(
                f"Forced alignment does not cover the exact script: {text}"
            )
        duration = cue["end"] - cue["start"]
        previous_start = -1
        for i, word in enumerate(words):
            start, end = word["start"], word["end"]
            if (
                not math.isfinite(start + end)
                or start < 0
                or end <= start
                or start < previous_start
                or end > duration + 0.03
            ):
                raise ValueError(
                    f"Invalid or uncertain alignment; cannot change subtitle grouping: {text}"
                )
            boundaries[position] = i
            position += len(normalized(word["text"]))
            previous_start = start
        boundaries[position] = len(words)
        local = []
        for j, group in enumerate(planned["groups"]):
            if (
                group["char_start"] not in boundaries
                or group["char_end"] not in boundaries
            ):
                raise ValueError("Subtitle split falls inside an aligned token")
            first, last = (
                boundaries[group["char_start"]],
                boundaries[group["char_end"]] - 1,
            )
            onset, offset = words[first]["start"], words[last]["end"]
            # Bind the first caption to the known PCM clip start, including
            # leading room tone. An inferred voice onset must not delay it.
            start = (
                0.0
                if j == 0
                else max(0, onset - plan["lead_seconds"], words[first - 1]["end"])
            )
            end = min(duration, offset + 0.12)
            local.append({"text": group["text"], "start": start, "end": end})
            references.append(
                {
                    "id": group["id"],
                    "text": group["text"],
                    "speech_start": cue["start"] + onset,
                    "speech_end": cue["start"] + offset,
                    "last_character_anchor": cue["start"] + offset,
                    "first_in_utterance": j == 0,
                    "utterance_start": cue["start"],
                    "audio_sha256": checksum,
                }
            )
        for previous, following in pairwise(local):
            previous["end"] = min(previous["end"], following["start"])
        for part in local:
            if part["end"] <= part["start"]:
                raise ValueError(
                    "Caption has no display interval; refusing to merge lines"
                )
            result.append(
                {
                    **part,
                    "start": cue["start"] + part["start"],
                    "end": cue["start"] + part["end"],
                }
            )
        audit.append(
            {
                "text": text,
                "file_start": cue["start"],
                "file_end": cue["end"],
                "audio_sha256": checksum,
                "characters": words,
                "phrases": local,
            }
        )
    if plan.get("switch") == "previous_speech_end":
        for i, (part, reference) in enumerate(zip(result, references)):
            switch_at = (
                cues[0]["start"]
                if i == 0
                else min(cues[i]["start"], references[i - 1]["speech_end"])
            )
            part["start"] = switch_at
            reference.update(start_basis="previous_speech_end", switch_at=switch_at)
        for i, (part, reference) in enumerate(zip(result, references)):
            end = (
                result[i + 1]["start"]
                if i + 1 < len(result)
                else (narration_end if narration_end is not None else cues[-1]["end"])
            )
            if end <= part["start"]:
                raise ValueError(
                    "Invalid sentence end; cannot schedule immediate caption transition"
                )
            part["end"] = end
            reference.update(
                expected_display_end=end,
                end_basis="sentence_transition" if i + 1 < len(result) else "video_end",
            )
        for utterance, part in zip(audit, result, strict=True):
            utterance["phrases"] = [
                {
                    "text": part["text"],
                    "start": part["start"] - utterance["file_start"],
                    "end": part["end"] - utterance["file_start"],
                }
            ]
    validate_caption_plan(result, plan)
    return result, {
        "schema": SCHEMA,
        "method": "fixed subtitle lines; Qwen forced alignment; "
        + (
            "next sentence displayed at previous speech end"
            if plan.get("switch") == "previous_speech_end"
            else "first caption at PCM clip start"
        ),
        "model_sha256": alignment["model_sha256"],
        "plan": plan,
        "references": references,
        "utterances": audit,
    }
