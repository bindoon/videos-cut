"""Fixed subtitle lines are the user contract; alignment may not merge them."""

import hashlib
import wave

import numpy as np
import pytest

from videocut.captions import (
    align_script_cues,
    create_caption_plan,
    validate_caption_plan,
)
from videocut.speech import build_narration, read_srt


def fixture_audio(tmp_path):
    path = tmp_path / "speech.wav"
    samples = np.zeros(5 * 48000, dtype="<i2")
    samples[14400:57600] = 6000
    samples[79200:172800] = 6000
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(samples.tobytes())
    text = "喜欢清爽，就喝一口黑咖啡。"
    spans = [
        (0.30, 0.50),
        (0.50, 0.70),
        (0.70, 0.90),
        (0.90, 1.20),
        (1.65, 1.9),
        (1.9, 2.2),
        (2.2, 2.4),
        (2.4, 2.6),
        (2.6, 2.9),
        (2.9, 3.2),
        (3.2, 3.6),
    ]
    chars = [c for c in text if c.isalnum()]
    alignment = {
        "schema": "qwen-forced-v1",
        "model_sha256": "fixture",
        "utterances": [
            {
                "expected": text,
                "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "words": [
                    {"text": c, "start": a, "end": b} for c, (a, b) in zip(chars, spans)
                ],
            }
        ],
    }
    return path, text, alignment


def test_first_caption_starts_with_audio_clip_and_next_line_has_own_time(tmp_path):
    path, text, alignment = fixture_audio(tmp_path)
    cues, audit = align_script_cues(
        [{"text": text, "start": 10, "end": 15}],
        {text: path},
        alignment,
        create_caption_plan(
            {"scenes": [{"lines": [text]}], "caption_layout": "phrases"}
        ),
    )
    assert [c["text"] for c in cues] == ["喜欢清爽，", "就喝一口黑咖啡。"]
    assert cues[0]["start"] == 10  # exact PCM clip start, not an estimated voice onset
    assert cues[1]["start"] == pytest.approx(11.45)
    assert cues[0]["end"] <= cues[1]["start"]
    assert audit["references"][0]["speech_start"] == 10.3


def test_different_voice_checksum_is_rejected(tmp_path):
    path, text, alignment = fixture_audio(tmp_path)
    alignment["utterances"][0]["audio_sha256"] = "stale"
    with pytest.raises(ValueError, match="different audio"):
        align_script_cues(
            [{"text": text, "start": 0, "end": 5}], {text: path}, alignment
        )


def test_old_ctc_fallback_cannot_change_subtitle_lines(tmp_path):
    path, text, alignment = fixture_audio(tmp_path)
    alignment["schema"] = "ctc-forced-v1"
    with pytest.raises(ValueError, match="regenerated"):
        align_script_cues(
            [{"text": text, "start": 0, "end": 5}], {text: path}, alignment
        )


def test_invalid_alignment_fails_instead_of_merging(tmp_path):
    path, text, alignment = fixture_audio(tmp_path)
    alignment["utterances"][0]["words"][4]["end"] = 1.65
    with pytest.raises(ValueError, match="cannot change subtitle grouping"):
        align_script_cues(
            [{"text": text, "start": 0, "end": 5}], {text: path}, alignment
        )


def test_explicit_display_lines_must_preserve_the_script(tmp_path):
    _, text, _ = fixture_audio(tmp_path)
    config = {
        "scenes": [{"lines": [text]}],
        "subtitle_phrases": {text: ["喜欢清爽", "喝茶"]},
    }
    with pytest.raises(ValueError, match="exact narration"):
        create_caption_plan(config)


def test_merging_two_planned_lines_is_rejected():
    text = "喜欢清爽，就喝一口黑咖啡。"
    plan = create_caption_plan(
        {"scenes": [{"lines": [text]}], "caption_layout": "phrases"}
    )
    with pytest.raises(ValueError, match="merging"):
        validate_caption_plan([{"text": text, "start": 0, "end": 4}], plan)


def test_explicit_single_line_is_allowed_only_when_planned(tmp_path):
    path, text, alignment = fixture_audio(tmp_path)
    plan = create_caption_plan(
        {"scenes": [{"lines": [text]}], "subtitle_phrases": {text: [text]}}
    )
    cues, _ = align_script_cues(
        [{"text": text, "start": 0, "end": 5}], {text: path}, alignment, plan
    )
    assert [c["text"] for c in cues] == [text]
    assert cues[0]["start"] == 0


def test_plan_exists_before_tts_and_renderer_receives_serialized_srt(
    tmp_path, monkeypatch
):
    path, text, alignment = fixture_audio(tmp_path)
    output = tmp_path / "output"
    output.mkdir()

    def synthesize(*args, **kwargs):
        assert (output / "caption-plan.json").is_file()
        return path

    monkeypatch.setattr("videocut.speech.synthesize_line", synthesize)
    _, cues, _ = build_narration(
        {"scenes": [{"lines": [text]}], "caption_layout": "phrases"},
        output,
        "indextts",
        align_to_speech=True,
        word_alignment=alignment,
    )
    assert cues == read_srt(output / "captions.srt")
    assert cues[0]["start"] == 0
    assert len(cues) == 2


def test_explicit_audio_clip_switch_does_not_need_word_alignment(tmp_path, monkeypatch):
    path, text, _ = fixture_audio(tmp_path)
    output = tmp_path / "whole-sentence"
    output.mkdir()

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "A full audio clip caption does not require estimated word times"
        )

    monkeypatch.setattr("videocut.captions.collect_alignment", forbidden)
    _, cues, _ = build_narration(
        {"scenes": [{"lines": [text]}], "caption_switch": "audio_clip"},
        output,
        "indextts",
        {text: str(path)},
        align_to_speech=True,
    )
    assert cues == [{"text": text, "start": 0, "end": 5}]
    assert not (output / "qwen-alignment.json").exists()


def test_next_sentence_appears_at_previous_spoken_end_not_next_file_start(tmp_path):
    import copy
    import json

    path, text, alignment = fixture_audio(tmp_path)
    following = "喜欢温柔，就加一点牛奶。"
    record = copy.deepcopy(alignment["utterances"][0])
    record["expected"] = following
    chars = [c for c in following if c.isalnum()]
    record["words"] = [{**w, "text": c} for c, w in zip(chars, record["words"])]
    alignment["utterances"].append(record)
    output = tmp_path / "immediate"
    output.mkdir()
    _, cues, _ = build_narration(
        {"scenes": [{"lines": [text, following]}]},
        output,
        "indextts",
        {text: str(path), following: str(path)},
        align_to_speech=True,
        word_alignment=alignment,
    )
    assert cues[0]["start"] == 0
    assert cues[0]["end"] == cues[1]["start"] == 3.6
    assert cues[1]["end"] == 10.74
    report = json.loads((output / "caption-alignment.json").read_text())
    assert report["references"][1]["utterance_start"] == 5.12
    assert report["references"][1]["switch_at"] == 3.6
