from videocut.cleaning import (
    filler_intervals,
    keep_intervals,
    map_time,
    merge_intervals,
)
from videocut.speech import srt_time


def test_overlapping_cuts_preserve_timeline_and_conserve_duration():
    removed = merge_intervals([(-1, 2), (1, 3), (5, 7), (6, 9), (12, 15)], 12)
    kept = keep_intervals(removed, 12)
    assert kept == [(3, 5), (9, 12)]
    assert sum(b - a for a, b in kept) + sum(b - a for a, b in removed) == 12
    assert map_time(9, kept) == 2
    assert map_time(10.5, kept) == 3.5
    assert map_time(6, kept) == 2


def test_filler_does_not_cut_a_substring_of_a_meaningful_word():
    words = [
        {"text": "summer", "start": 0, "end": 1},
        {"text": "um,", "start": 1.2, "end": 1.5},
        {"text": "那", "start": 2, "end": 2.2},
        {"text": "个，", "start": 2.2, "end": 2.4},
        {"text": "那个东西", "start": 3, "end": 4},
    ]
    result = filler_intervals(words, ["um", "那个"])
    assert [(r["start"], r["end"]) for r in result] == [(1.2, 1.5), (2, 2.4)]


def test_filler_phrase_does_not_bridge_a_pause_between_separate_words():
    assert not filler_intervals(
        [
            {"text": "那", "start": 0, "end": 0.1},
            {"text": "个", "start": 1, "end": 1.2},
        ],
        ["那个"],
    )


def test_time_rounding_does_not_produce_an_invalid_60_second_timestamp():
    assert srt_time(59.9996) == "00:01:00,000"


def test_no_cuts_and_all_cuts():
    assert keep_intervals([], 10) == [(0, 10)]
    assert keep_intervals([(0, 10)], 10) == []


def test_chinese_filler_script_variants_match_the_same_configured_word():
    words = [
        {"text": "那個，", "start": 0, "end": 0.5},
        {"text": "就是說", "start": 1, "end": 1.5},
    ]
    assert len(filler_intervals(words, ["那个", "就是说"])) == 2
