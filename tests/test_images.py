"""Observable image results from real FFmpeg frames, with cache/failure recovery."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

from videocut.image_cards import plan_cards, render_cards, verify_cards
from videocut.image_ops import grab_frame, preview_band, sample_frames, sha256
from videocut.media import run
from videocut.render import find_font, inspect_output
from videocut.text_index import build_index


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    root = tmp_path_factory.mktemp("image-source")
    font = ImageFont.truetype(find_font(), 20)
    for i in range(24):
        n = i // 4
        image = Image.new("RGB", (320, 180), (30 + 30 * n, 60, 110))
        draw = ImageDraw.Draw(image)
        draw.ellipse((140, 20, 180, 60), fill="white")
        draw.rectangle((0, 126, 319, 179), fill=(10, 10, 10))
        draw.text((40, 140), f"Real subtitle {n}", font=font, fill="white")
        image.save(root / f"frame-{i:03d}.png")
    path = root / "source with space.mkv"
    run(["ffmpeg", "-v", "error", "-framerate", "4", "-i", str(root / "frame-%03d.png"),
         "-c:v", "ffv1", str(path)])
    # All seeks must decode from a single long GOP, rather than snap to its start.
    gop = root / "long-gop.mp4"
    run(["ffmpeg", "-v", "error", "-i", str(path), "-c:v", "libx264", "-g", "240",
         "-sc_threshold", "0", str(gop)])
    return path, root, gop


def manifest(tmp_path, source, *, mode="native", two=False):
    video, _, _ = source
    data = {"schema": "image-cards-v1", "source": str(video), "mode": mode,
            "style": {"width": 320, "band": [0.7, 1.0]},
            "cards": [{"id": "first", "lines": [{"time": t} for t in (0.5, 1.5, 2.5)]}]}
    if two:
        data["cards"].append({"id": "second", "lines": [{"time": t} for t in (3.5, 4.5, 5.5)]})
    if mode == "script":
        data["style"].update(font_size=18, hero_fraction=0.55)
        for card in data["cards"]:
            for line in card["lines"]:
                line.update(text="核对后的台词", reviewed=True,
                            text_source={"kind": "user", "reference": "test author script"})
    path = dump(tmp_path / "manifest.json", data)
    return path, data


def test_sample_exact_long_gop_and_aspect(source, tmp_path):
    _, root, gop = source
    frame = grab_frame(gop, 4.5, 6)
    assert frame.size == (320, 180)
    r, g, b = frame.getpixel((20, 20))
    assert abs(r - 150) < 8 and abs(g - 60) < 8 and abs(b - 110) < 8
    result = sample_frames(gop, tmp_path / "candidates", times=[1.5], around=0.25)
    assert [r["time"] for r in result["frames"]] == [1.25, 1.5, 1.75]
    with Image.open(tmp_path / "candidates/contact-sheet.jpg") as sheet:
        # A landscape frame is letterboxed in the 320x240 tile, not stretched.
        assert max(sheet.getpixel((160, 4))) < 40
        assert min(sheet.getpixel((160, 30 + 40))) > 200
    assert (root / "frame-000.png").is_file()
    with pytest.raises(ValueError, match="before video end"):
        sample_frames(gop, tmp_path / "bad", times=[6])
    assert not (tmp_path / "bad").exists()


def test_band_keeps_source_pixels(source, tmp_path):
    video, root, _ = source
    preview_band(video, tmp_path / "band", time=1.5, band=[0.7, 1.0])
    with Image.open(root / "frame-006.png") as frame, Image.open(tmp_path / "band/band.png") as crop:
        assert ImageChops.difference(frame.crop((0, 126, 320, 180)), crop).getbbox() is None


def test_native_is_one_uniform_pixel_stack(source, tmp_path):
    path, _ = manifest(tmp_path, source)
    before = sha256(source[0])
    report = render_cards(path, tmp_path / "cards")
    assert report["status"] == "ready" and report["reused"] == 0
    record = report["results"][0]
    assert record["text_origin"] == "source_pixels" and not record["text_boxes"]
    expected = Image.new("RGB", (320, 288))
    with Image.open(source[1] / "frame-002.png") as hero:
        expected.paste(hero, (0, 0))
    for index, n in enumerate((6, 10)):
        with Image.open(source[1] / f"frame-{n:03d}.png") as frame:
            expected.paste(frame.crop((0, 126, 320, 180)), (0, 180 + index * 54))
    with Image.open(tmp_path / "cards" / record["file"]) as actual:
        assert actual.size == expected.size
        assert max(ImageStat.Stat(ImageChops.difference(actual, expected)).mean) < 2
    verified = verify_cards(tmp_path / "cards/image-report.json")
    assert verified["mechanical_passed"] and not verified["semantic_verified"]
    assert verified["subtitle_sync"]["passed"] is None
    assert sha256(source[0]) == before
    with pytest.raises(FileExistsError):
        render_cards(path, tmp_path / "cards")


def test_script_draws_reviewed_text_and_reports_bounds(source, tmp_path):
    path, data = manifest(tmp_path, source, mode="script")
    report = render_cards(path, tmp_path / "cards")
    assert report["status"] == "ready"
    record = report["results"][0]
    assert record["text_origin"] == "post_added" and len(record["text_boxes"]) == 3
    assert (record["width"], record["height"]) == (320, 427)
    with Image.open(tmp_path / "cards" / record["file"]) as image:
        for left, top, right, bottom in record["text_boxes"]:
            pixels = image.crop((int(left), int(top), int(right), int(bottom))).convert("L")
            assert sum(pixels.histogram()[200:]) > 10  # Actual text pixels, not just a report.
    assert verify_cards(tmp_path / "cards/image-report.json")["mechanical_passed"]
    data["cards"][0]["lines"][1]["text"] = "字幕太长" * 100
    dump(path, data)
    failed = render_cards(path, tmp_path / "overflow")
    assert failed["status"] == "failed" and "height" in failed["failures"][0]["error"]
    assert failed["contact_sheet"] is None


@pytest.mark.parametrize("mutation,match", [
    (lambda d: d.update(mode="auto"), "explicitly"),
    (lambda d: d["cards"][0].update(id="../escape"), "safe"),
    (lambda d: d["cards"][0]["lines"][1].update(time=0.5), "strictly"),
    (lambda d: d["cards"][0]["lines"][0].update(text="Not native"), "native"),
    (lambda d: d["style"].update(font_size=40), "preserves pixels"),
    (lambda d: d.update(source_sha256="0" * 64), "checksum"),
])
def test_invalid_contract_is_rejected_before_writing(source, tmp_path, mutation, match):
    path, data = manifest(tmp_path, source)
    mutation(data)
    dump(path, data)
    with pytest.raises(ValueError, match=match):
        render_cards(path, tmp_path / "never-written")
    assert not (tmp_path / "never-written").exists()


def test_script_requires_review_and_provenance(source, tmp_path):
    path, data = manifest(tmp_path, source, mode="script")
    data["cards"][0]["lines"][0]["reviewed"] = False
    dump(path, data)
    with pytest.raises(ValueError, match="reviewed"):
        plan_cards(path)
    data["cards"][0]["lines"][0]["reviewed"] = True
    del data["cards"][0]["lines"][0]["text_source"]
    dump(path, data)
    with pytest.raises(ValueError, match="text_source"):
        plan_cards(path)


def test_missing_glyph_is_rejected_before_creating_output(source, tmp_path):
    path, data = manifest(tmp_path, source, mode="script")
    data["cards"][0]["lines"][0]["text"] = chr(0x10FFFF)
    dump(path, data)
    with pytest.raises(ValueError, match="no glyph"):
        render_cards(path, tmp_path / "missing-glyph")
    assert not (tmp_path / "missing-glyph").exists()


def test_resume_reuses_unchanged_cards_and_repairs_corruption(source, tmp_path):
    path, data = manifest(tmp_path, source, two=True)
    output = tmp_path / "cards"
    first = render_cards(path, output)
    assert render_cards(path, output, resume=True)["reused"] == 2
    data["cards"][0]["lines"][0]["time"] = 0.75
    dump(path, data)
    changed = render_cards(path, output, resume=True)
    assert changed["reused"] == 1
    assert changed["results"][0]["file"] != first["results"][0]["file"]
    assert (output / first["results"][0]["file"]).is_file()  # Keep earlier revision.
    image = output / changed["results"][1]["file"]
    payload = bytearray(image.read_bytes())
    payload[-15] ^= 1
    image.write_bytes(payload)
    with pytest.raises(ValueError, match="checksum/geometry"):
        verify_cards(output / "image-report.json")
    repaired = render_cards(path, output, resume=True)
    assert repaired["reused"] == 1 and repaired["status"] == "ready"
    assert verify_cards(output / "image-report.json")["mechanical_passed"]
    data["style"]["strip_gap"] = 2
    dump(path, data)
    assert render_cards(path, output, resume=True)["reused"] == 0


def test_font_and_source_changes_invalidate_cache(source, tmp_path):
    path, data = manifest(tmp_path, source, mode="script")
    font = tmp_path / "font.ttc"
    font.write_bytes(Path(find_font()).read_bytes())
    video = tmp_path / "source.mkv"
    video.write_bytes(source[0].read_bytes())
    data["source"] = str(video)
    data["style"]["font"] = str(font)
    dump(path, data)
    output = tmp_path / "cards"
    render_cards(path, output)
    font.write_bytes(font.read_bytes() + b"font-revision")
    assert render_cards(path, output, resume=True)["reused"] == 0
    video.write_bytes(video.read_bytes() + b"source-revision")
    assert render_cards(path, output, resume=True)["reused"] == 0


def test_partial_failure_recovery_and_duplicate_guard(source, tmp_path):
    path, data = manifest(tmp_path, source, two=True)
    good = copy.deepcopy(data)
    data["cards"][1]["lines"] = [{"time": t} for t in (3.05, 3.1, 3.15)]
    dump(path, data)
    output = tmp_path / "cards"
    report = render_cards(path, output, keep_going=True)
    assert report["status"] == "failed" and report["results"][0]["status"] == "ready"
    assert "Repeated subtitle" in report["failures"][0]["error"]
    assert report["contact_sheet"] is None
    with pytest.raises(ValueError, match="incomplete"):
        verify_cards(output / "image-report.json")
    dump(path, good)
    report = render_cards(path, output, resume=True)
    assert report["status"] == "ready" and report["reused"] == 1


def test_resume_recovers_unregistered_images_without_overwriting(source, tmp_path):
    path, _ = manifest(tmp_path, source)
    output = tmp_path / "cards"
    first = render_cards(path, output)
    original = output / first["results"][0]["file"]
    original_hash = sha256(original)
    first.update(status="running", results=[], contact_sheet=None)
    dump(output / "image-report.json", first)
    recovered = render_cards(path, output, resume=True)
    assert recovered["status"] == "ready" and recovered["reused"] == 0
    assert "recovered" in recovered["results"][0]["file"]
    assert sha256(original) == original_hash
    assert render_cards(path, output, resume=True)["reused"] == 1


def test_track_index_deduplicates_without_claiming_native_or_human(source, tmp_path):
    track = tmp_path / "rolling.vtt"
    track.write_text("WEBVTT\n\n00:00.000 --> 00:01.500\nHello\n\n"
                     "00:01.000 --> 00:02.500\nHello world\n\n"
                     "00:02.000 --> 00:03.000\nHello world\n\n"
                     "00:04.000 --> 00:05.000\nHello world\n", encoding="utf-8")
    result = build_index(track, source[0], tmp_path / "index.json")
    assert result["input_cues"] == 4 and len(result["cues"]) == 2
    assert result["cues"][0] == {"start": 0, "end": 3, "text": "Hello world",
                                   "source_cues": [0, 1, 2], "candidate_time": 1.5}
    assert result["track"]["generation"] == "unspecified"
    assert result["burned_in_subtitles"] == "unverified"


def test_asr_index_binds_source_and_accepts_no_speech(source, tmp_path):
    track = dump(tmp_path / "asr.json", {"source_sha256": sha256(source[0]), "segments": [],
                                         "status": "no_speech"})
    result = build_index(track, source[0], tmp_path / "index.json", kind="asr")
    assert result["cues"] == []
    dump(track, {"source_sha256": "wrong", "segments": []})
    with pytest.raises(ValueError, match="source_sha256"):
        build_index(track, source[0], tmp_path / "bad.json", kind="asr")


def test_cli_plan_is_read_only_and_works_outside_repo(source, tmp_path):
    path, _ = manifest(tmp_path, source)
    before = set(tmp_path.iterdir())
    result = subprocess.run([sys.executable, "-m", "videocut.image_cli", "plan", "--manifest", str(path)],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    # Test installation supplies the module; no repository-relative asset paths.
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mode"] == "native"
    assert set(tmp_path.iterdir()) == before


def test_landscape_render_overview_preserves_geometry(tmp_path):
    video = tmp_path / "landscape.mp4"
    run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=4:d=1",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(video)])
    inspect_output(video, tmp_path, 1)
    with Image.open(tmp_path / "contact-sheet.jpg") as sheet:
        assert max(sheet.getpixel((120, 10))) < 40
        assert sheet.getpixel((120, 210))[0] > 220
