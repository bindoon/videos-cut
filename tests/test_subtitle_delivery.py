import copy
import json
import wave

import numpy as np
import pytest

from videocut.captions import create_caption_plan
from videocut.media import run
from videocut.render import compose
from videocut.speech import write_srt
from videocut.sync import check_boundaries, verify_subtitle_sync


def test_one_second_delay_is_rejected_even_when_plan_and_pixels_agree():
    cues = [{"text": "你好", "start": 1.3, "end": 2.5}]
    reference = [{"text": "你好", "speech_start": 0.3}]
    pixels = [{"start": 1.333, "end": 2.5}]
    errors, _ = check_boundaries(cues, reference, pixels, 24)
    assert any("Subtitle/speech onset" in e for e in errors)


def test_missing_rendered_caption_is_rejected():
    errors, _ = check_boundaries(
        [{"text": "你好", "start": 0.2, "end": 1.5}],
        [{"text": "你好", "speech_start": 0.3}],
        [None],
        24,
    )
    assert any("Missing" in e for e in errors)


def test_subtitle_disappearing_before_speech_ends_is_rejected():
    errors, _ = check_boundaries(
        [{"text": "早晨", "start": 0.2, "end": 0.6}],
        [{"text": "早晨", "speech_start": 0.28, "speech_end": 1.0}],
        [{"start": 0.208, "end": 0.625}],
        24,
    )
    assert any("ending" in e for e in errors)


@pytest.mark.parametrize("timing_mode", ["qwen", "pcm", "sentence_end"])
def test_actual_moviepy_video_is_checked_and_delayed_video_fails(tmp_path, timing_mode):
    # Real encoded frames/audio, independent known acoustic windows. No ASR,
    # model download, mock renderer, or report copied from planned cue times.
    rate = 48000
    rng = np.random.default_rng(41)
    pcm = np.zeros(rate * 4, dtype="<i2")
    for a, b in [(0.4, 1.2), (2.0, 2.8)]:
        left, right = round(a * rate), round(b * rate)
        pcm[left:right] = (rng.normal(0, 0.05, right - left) * 32767).astype("<i2")
    narration = tmp_path / "voice.wav"
    with wave.open(str(narration), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm.tobytes())
    background = tmp_path / "background.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x394039:s=360x640:r=24:d=4",
            "-c:v",
            "libx264",
            str(background),
        ]
    )
    config = {"width": 360, "height": 640, "fps": 24, "title": "同步测试"}
    scenes = [{"start": 0, "duration": 4}]
    cues = [
        {"text": "第一句，", "start": 0, "end": 1.3},
        {"text": "第二句话。", "start": 1.8, "end": 2.9},
    ]
    alignment = {
        "schema": "qwen-forced-v1",
        "plan": create_caption_plan(
            {"scenes": [{"lines": ["第一句，第二句话。"]}], "caption_layout": "phrases"}
        ),
        "references": [
            {
                "text": "第一句，",
                "speech_start": 0.4,
                "last_character_anchor": 1.2,
                "first_in_utterance": True,
                "utterance_start": 0,
            },
            {"text": "第二句话。", "speech_start": 2.0, "last_character_anchor": 2.8},
        ],
    }
    if timing_mode == "pcm":
        alignment = {
            "schema": "pcm-caption-v1",
            "plan": create_caption_plan(
                {
                    "scenes": [{"lines": [c["text"] for c in cues]}],
                    "caption_switch": "audio_clip",
                }
            ),
            "references": [
                {
                    "text": c["text"],
                    "audio_start": c["start"],
                    "audio_end": c["end"],
                    "utterance_start": c["start"],
                    "utterance_end": c["end"],
                    "first_in_utterance": True,
                    "end_basis": "audio_clip_end",
                }
                for c in cues
            ],
        }
    if timing_mode == "sentence_end":
        cues[0]["end"] = 1.2
        cues[1].update(start=1.2, end=4.0)
        alignment["plan"] = create_caption_plan(
            {"scenes": [{"lines": [c["text"] for c in cues]}]}
        )
        alignment["references"][0].update(
            start_basis="previous_speech_end",
            switch_at=0,
            expected_display_end=1.2,
            speech_end=1.2,
            end_basis="sentence_transition",
        )
        alignment["references"][1].update(
            first_in_utterance=True,
            utterance_start=1.8,
            start_basis="previous_speech_end",
            switch_at=1.2,
            expected_display_end=4.0,
            speech_end=2.8,
            end_basis="video_end",
        )
    good = tmp_path / "good"
    good.mkdir()
    write_srt(cues, good / "captions.srt")
    video = compose(config, background, scenes, cues, narration, [], good)
    report = verify_subtitle_sync(video, config, cues, alignment, narration, good)
    assert report["passed"]
    assert report["pixel_detection"]["matched_runs"] == 2
    assert report["caption_measurements"][0]["visible_start"] == 0
    if timing_mode == "sentence_end":
        assert report["pixel_detection"]["unrecognized_frames"] == 0
        assert (
            report["caption_measurements"][0]["visible_end"]
            == report["caption_measurements"][1]["visible_start"]
            == 1.2083333333333333
        )
    delayed = copy.deepcopy(cues)
    for cue in delayed:
        cue["start"] += 1
        cue["end"] += 1
    bad = tmp_path / "bad"
    bad.mkdir()
    write_srt(delayed, bad / "captions.srt")
    video = compose(
        config,
        background,
        scenes,
        delayed,
        narration,
        [],
        bad,
        target_name="candidate.mp4",
    )
    with pytest.raises(ValueError, match="Subtitle synchronization failed"):
        verify_subtitle_sync(video, config, delayed, alignment, narration, bad)
    rejected = json.loads((bad / "subtitle-sync-verification.json").read_text())
    for incorrect, correct in zip(
        rejected["caption_measurements"], report["caption_measurements"]
    ):
        assert incorrect["visible_start"] - correct["visible_start"] == pytest.approx(
            1, abs=1 / 24
        )
    assert not (bad / "final.mp4").exists()
    assert any(
        (
            "Subtitle/speech onset"
            if timing_mode in {"qwen", "sentence_end"}
            else "First subtitle must start"
        )
        in reason
        for reason in rejected["failures"]
    )
