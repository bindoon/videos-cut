"""Verify speech timing and the subtitle pixels in the delivered video."""

from __future__ import annotations

import hashlib
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .media import decode_audio, probe, write_json
from .render import make_text


def check_boundaries(cues, references, observed, fps):
    """Compare three timelines: acoustic anchors, planned cues, decoded pixels."""
    failures, measurements = [], []
    if not (len(cues) == len(references) == len(observed)):
        return ["Caption/reference/detected counts differ"], []
    for cue, reference, visible in zip(cues, references, observed):
        row = {
            "text": cue["text"],
            "planned_start": cue["start"],
            "speech_start": reference.get("speech_start"),
            "visible_start": None,
            "visible_end": None,
        }
        if cue["text"] != reference["text"] or visible is None:
            failures.append(f"Missing or wrong rendered caption: {cue['text']}")
        else:
            row.update(visible_start=visible["start"], visible_end=visible["end"])
            if "speech_start" in reference:
                late = visible["start"] - reference["speech_start"]
                early = -late
                row["display_minus_speech_seconds"] = late
                if late > 0.18 or (
                    early > 0.25 and not reference.get("first_in_utterance")
                ):
                    failures.append(
                        f"Subtitle/speech onset differs by {late:+.3f}s: {cue['text']}"
                    )
            if reference.get("first_in_utterance"):
                clip_delta = visible["start"] - reference["utterance_start"]
                row["display_minus_clip_start_seconds"] = clip_delta
                if reference.get("start_basis") == "previous_speech_end":
                    switch_delta = visible["start"] - reference["switch_at"]
                    row["display_minus_previous_speech_end_seconds"] = switch_delta
                    if abs(switch_delta) > 1 / fps + 0.001:
                        failures.append(
                            f"Subtitle must switch immediately after previous speech: {cue['text']}"
                        )
                elif abs(clip_delta) > 1 / fps + 0.001:
                    failures.append(
                        f"First subtitle must start with its audio clip: {cue['text']}"
                    )
            if reference.get("end_basis") == "audio_clip_end":
                clip_end_delta = visible["end"] - reference["utterance_end"]
                row["display_minus_clip_end_seconds"] = clip_end_delta
                if abs(clip_end_delta) > 1 / fps + 0.001:
                    failures.append(
                        f"Full sentence subtitle must end with its audio clip: {cue['text']}"
                    )
            if "expected_display_end" in reference and (
                abs(visible["end"] - reference["expected_display_end"])
                > 1 / fps + 0.001
            ):
                failures.append(
                    f"Subtitle must remain visible until the next sentence transition: {cue['text']}"
                )
            if abs(visible["start"] - cue["start"]) > 2 / fps:
                failures.append(
                    f"Rendered subtitle start differs from plan: {cue['text']}"
                )
            if abs(visible["end"] - cue["end"]) > 2 / fps:
                failures.append(
                    f"Rendered subtitle end differs from plan: {cue['text']}"
                )
            if "speech_end" in reference and reference.get("end_basis") != "video_end":
                end_delta = visible["end"] - reference["speech_end"]
                row["end_minus_speech_seconds"] = end_delta
                if end_delta < -0.12 or end_delta > 0.25:
                    failures.append(
                        f"Subtitle/speech ending differs by {end_delta:+.3f}s: {cue['text']}"
                    )
        measurements.append(row)
    return failures, measurements


def _dilate(mask):
    return (
        np.asarray(
            Image.fromarray(mask.astype("uint8") * 255).filter(ImageFilter.MaxFilter(3))
        )
        > 0
    )


def detect_caption_pixels(video, config, cues):
    """Match glyphs in every decoded frame; timing never comes from cue JSON.

    This is deliberately limited to the pipeline's unanimated subtitle style.
    A style/font change that cannot be recognized fails verification.
    """
    info = probe(video)
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    numerator, denominator = map(int, stream["avg_frame_rate"].split("/"))
    fps = numerator / denominator
    if abs(float(stream.get("start_time", 0))) > 1 / fps:
        raise ValueError("Subtitle verification requires a zero-based video timeline")
    w, h = config["width"], config["height"]
    width, y, size = int(w * 0.88), round(h * 0.785), round(w * 0.050)
    texts = list(dict.fromkeys(c["text"] for c in cues))
    images = [
        np.asarray(make_text(t, width, size, color="#fff8e7", pill=True)) for t in texts
    ]
    height = max(i.shape[0] for i in images)
    masks = []
    for array in images:
        mask = np.zeros((height, width), dtype=bool)
        mask[: array.shape[0]] = array[:, :, 3] > 220
        masks.append(mask)
    expanded = [_dilate(m) for m in masks]
    positions = [np.where(m) for m in masks]
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(video),
        "-an",
        "-vf",
        f"format=rgb24,crop={width}:{height}:{(w - width) // 2}:{y}",
        "-fps_mode",
        "passthrough",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    labels, confidences = [], []
    try:
        while raw := process.stdout.read(width * height * 3):
            if len(raw) != width * height * 3:
                raise ValueError("Truncated decoded subtitle frame")
            pixels = np.frombuffer(raw, dtype="uint8").reshape(height, width, 3)
            white = (
                (pixels[:, :, 0] > 205)
                & (pixels[:, :, 1] > 200)
                & (pixels[:, :, 2] > 180)
                & (pixels[:, :, 0].astype(int) - pixels[:, :, 1] < 30)
            )
            white_count = int(white.sum())
            if white_count < 20:
                labels.append(-1)
                confidences.append(0)
                continue
            grown = _dilate(white)
            scores = []
            for coords, mask in zip(positions, expanded):
                recall = float(grown[coords].mean())
                precision = np.count_nonzero(white & mask) / white_count
                scores.append(2 * recall * precision / max(1e-8, recall + precision))
            best = int(np.argmax(scores))
            labels.append(best if scores[best] >= 0.78 else -1)
            confidences.append(scores[best])
        error = process.stderr.read().decode(errors="replace")
        if process.wait(timeout=60):
            raise ValueError(f"Cannot decode subtitle frames: {error[-1000:]}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    # Each planned occurrence must be an independent contiguous visible run.
    runs = []
    for frame, label in enumerate(labels):
        if label < 0:
            continue
        if runs and runs[-1]["label"] == label and runs[-1]["last"] == frame - 1:
            runs[-1]["last"] = frame
        else:
            runs.append({"label": label, "first": frame, "last": frame})
    observed, used = [], set()
    for cue in cues:
        choices = [
            (i, r)
            for i, r in enumerate(runs)
            if i not in used and texts[r["label"]] == cue["text"]
        ]
        if not choices:
            observed.append(None)
            continue
        index, run = min(choices, key=lambda v: abs(v[1]["first"] / fps - cue["start"]))
        used.add(index)
        observed.append({"start": run["first"] / fps, "end": (run["last"] + 1) / fps})
    return (
        observed,
        fps,
        {
            "decoded_frames": len(labels),
            "matched_runs": len(used),
            "unexpected_runs": len(runs) - len(used),
            "unrecognized_frames": labels.count(-1),
        },
    )


def verify_subtitle_sync(video: Path, config, cues, alignment, narration, output):
    failures = []
    observed, fps, pixel_audit = detect_caption_pixels(video, config, cues)
    if alignment.get("schema") not in {
        "qwen-forced-v1",
        "ctc-forced-v1",
        "pcm-caption-v1",
    }:
        raise ValueError(
            "Speech synchronization requires given-script forced alignment"
        )
    if alignment.get("schema") in {"qwen-forced-v1", "pcm-caption-v1"}:
        from .captions import validate_caption_plan
        from .speech import read_srt

        serialized = read_srt(output / "captions.srt")
        validate_caption_plan(serialized, alignment["plan"])
        if serialized != cues:
            raise ValueError("Rendered subtitle timeline differs from the SRT")
    problems, measurements = check_boundaries(
        cues, alignment["references"], observed, fps
    )
    failures.extend(problems)
    if pixel_audit["unexpected_runs"]:
        failures.append("Unexpected or fragmented subtitle runs in final frames")
    if (
        alignment.get("plan", {}).get("switch") == "previous_speech_end"
        and pixel_audit["unrecognized_frames"]
    ):
        failures.append(
            "Immediate sentence transitions must have no blank subtitle frames"
        )
    # Independently compare final encoded voice timeline at distributed windows.
    original, encoded = decode_audio(narration, 8000), decode_audio(video, 8000)
    wave_checks = []
    for reference in alignment["references"]:
        if alignment["schema"] == "pcm-caption-v1":
            start, end = reference["audio_start"], reference["audio_end"]
        else:
            start, end = reference["speech_start"], reference["last_character_anchor"]
        # A midpoint can land in an intra-phrase pause, where backing music
        # dominates correlation. Select the strongest 0.5 s of source voice.
        window = min(4000, max(1600, int((end - start) * 8000)))
        candidates = range(
            max(0, int(start * 8000)),
            min(len(original) - window, int(end * 8000) - window) + 1,
            800,
        )
        choices = list(candidates)
        if not choices:
            failures.append(
                f"Too little speech for final audio verification: {reference['text']}"
            )
            continue
        left = max(
            choices,
            key=lambda i: float(
                np.dot(original[i : i + window], original[i : i + window])
            ),
        )
        right = left + window
        center = (left + right) / 16000
        if right - left < 1600:
            continue
        fragment = original[left:right]
        # Scan +/- 0.5 seconds in 10 ms increments; music does not dominate voice.
        values = []
        for lag in range(-4000, 4001, 80):
            if left + lag < 0:
                continue
            candidate = encoded[left + lag : right + lag]
            if len(candidate) != len(fragment):
                continue
            score = float(
                np.dot(fragment, candidate)
                / max(
                    1e-10,
                    math.sqrt(
                        float(np.dot(fragment, fragment) * np.dot(candidate, candidate))
                    ),
                )
            )
            values.append((score, lag / 8000))
        score, lag = max(values)
        wave_checks.append({"time": center, "lag_seconds": lag, "correlation": score})
        if abs(lag) > 0.05 or score < 0.75:
            failures.append(
                f"Final audio differs from narration at {center:.3f}s: lag={lag}, corr={score:.3f}"
            )
    report = {
        "passed": not failures,
        "failures": failures,
        "caption_measurements": measurements,
        "pixel_detection": pixel_audit,
        "audio_checks": wave_checks,
        "limits": {
            "caption_late_seconds": 0.18,
            "caption_early_seconds": 0.25,
            "caption_end_early_seconds": 0.12,
            "caption_end_late_seconds": 0.25,
            "render_boundary_frames": 2,
            "audio_lag_seconds": 0.05,
        },
        "scope": "Fixed SRT lines, PCM clip starts, estimated speech boundaries and actual rendered pixels; not pronunciation or emotion",
    }
    if alignment.get("schema") in {"qwen-forced-v1", "pcm-caption-v1"}:
        report["timing_source"] = "captions.srt"
        report["srt_sha256"] = hashlib.sha256(
            (output / "captions.srt").read_bytes()
        ).hexdigest()
        report["fixed_caption_plan"] = True
        report["switch_policy"] = alignment["plan"].get("switch", "audio_clip")
        if report["switch_policy"] == "previous_speech_end":
            report["limits"]["sentence_switch_frames"] = 1
            report["limits"]["blank_subtitle_frames"] = 0
            report["reading_note"] = (
                "Next sentence is intentionally visible before its own audio; its display start is checked against previous speech end, not its own onset."
            )
    write_json(output / "subtitle-sync-verification.json", report)
    if failures:
        raise ValueError(
            "Subtitle synchronization failed; candidate retained, no final published: "
            + "; ".join(failures[:4])
        )
    return report
