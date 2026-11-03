"""Acceptance of immutable preview versions, using actual FFmpeg and HTTP."""
import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from PIL import Image

from videocut import review
from videocut.ffmpeg_tools import invoke_json
from videocut.review_server import create_server


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    root = tmp_path_factory.mktemp("review-real-clips")
    outputs = []
    for name, color in [("first", (130, 60, 20)), ("changed", (20, 80, 160))]:
        folder = root / name
        folder.mkdir()
        for n in range(12):
            Image.new("RGB", (160, 90), tuple(v + n for v in color)).save(folder / f"frame_{n:03}.png")
        output = root / (name + ".mp4")
        invoke_json(["sequence", "--dir", str(folder), "--pattern", "frame_%03d.png", "--fps", "12", "-o", str(output), "--json"])
        outputs.append(output)
    return outputs


@pytest.fixture
def project(tmp_path):
    config = dump(tmp_path / "source/project.json", {
        "title": "真实预览", "width": 160, "height": 90, "fps": 12,
        "scenes": [{"id": "hero", "label": "主镜头", "start": 0, "duration": 1}],
    })
    return tmp_path / "review", config, tmp_path / "generated"


def stage(project, name="first", **options):
    root, config, outputs = project
    video = outputs / name / "preview.mp4"
    timeline = outputs / name / "timeline.json"
    draft = review.prepare(root, renderer="media", config=config, video=video, timeline=timeline, duration=1, **options)
    return draft, video, timeline


def produce(video, timeline, clip, *, scene_id="hero"):
    video.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(clip, video)
    dump(timeline, {"scenes": [{"id": scene_id, "label": "主镜头", "start": 0, "duration": 1}]})


def publish_first(project, clips):
    draft, video, timeline = stage(project)
    produce(video, timeline, clips[0])
    return review.publish(project[0], draft["id"])


def test_publish_uses_real_decoded_frames_and_seals_artifact(project, clips):
    doc = publish_first(project, clips)
    root = project[0]
    assert (doc["video"]["frames"], doc["video"]["fps"], doc["video"]["width"], doc["video"]["height"]) == (12, 12, 160, 90)
    assert doc["scenes"][0]["id"] == "hero"
    assert doc["checks"]["subtitle_sync"]["passed"] is None
    assert doc["checks"]["aesthetic"]["passed"] is None
    assert review.verify(root)["integrity"]["passed"]
    # The renderer's mutable output is not what viewers receive.
    (project[2] / "first/preview.mp4").write_bytes(b"changed after publish")
    assert review.verify(root)["integrity"]["passed"]
    assert review.state(root)["latest"] == doc["id"]


def test_native_image_montage_with_h264_side_data_can_be_published(project):
    from videocut.render import render_backgrounds
    root, config, outputs = project
    materials = []
    for i, color in enumerate(((160, 80, 30), (30, 100, 160))):
        file = config.parent / f"image-{i}.png"
        Image.new("RGB", (320, 180), color).save(file)
        materials.append({"id": f"image-{i}", "kind": "image", "path": str(file), "tags": []})
    scenes = [{"id": name, "label": name, "material_id": f"image-{i}", "kind": "image", "start": i*.5, "duration": .5}
              for i, name in enumerate(("hero", "second"))]
    document = {"title": "原生图片混剪", "width": 160, "height": 90, "fps": 12, "transition_seconds": .25, "scenes": scenes}
    dump(config, document)
    catalog = dump(config.parent / "materials.json", materials)
    draft = review.prepare(root, renderer="media", config=config, materials=catalog,
                           video=outputs / "background.mp4", timeline=outputs / "timeline.json", duration=1)
    outputs.mkdir()
    render_backgrounds(document, scenes, materials, outputs)
    doc = review.publish(root, draft["id"])
    assert doc["video"]["frames"] == 12
    assert [s["id"] for s in doc["scenes"]] == ["hero", "second"]


def test_rejects_old_candidate_source_changes_and_preserves_last_revision(project, clips):
    first = publish_first(project, clips)
    with pytest.raises(ValueError, match="already exists"):
        stage(project)
    draft, video, timeline = stage(project, "next")
    produce(video, timeline, clips[1])
    config = project[1]
    config.write_text(config.read_text().replace("真实预览", "已改稿"))
    with pytest.raises(ValueError, match="Source inputs changed"):
        review.publish(project[0], draft["id"])
    state = review.state(project[0])
    assert state["latest"] == first["id"]
    assert state["pending"]["changed_sources"] == [str(config)]
    review.abandon(project[0])
    assert review.state(project[0])["pending"] is None


def test_rejects_forged_duration_and_unknown_rendered_scene(project, clips):
    draft, video, timeline = stage(project)
    produce(video, timeline, clips[0], scene_id="invented")
    with pytest.raises(ValueError, match="unknown scene id"):
        review.publish(project[0], draft["id"])
    assert review.state(project[0])["latest"] is None
    review.abandon(project[0])
    root, config, outputs = project
    draft = review.prepare(root, renderer="media", config=config, video=outputs / "short.mp4", timeline=timeline, duration=2)
    shutil.copyfile(clips[0], outputs / "short.mp4")
    with pytest.raises(ValueError, match="frame count"):
        review.publish(root, draft["id"])


def test_explicit_stable_ids_are_required_and_duplicates_rejected(project):
    config = project[1]
    data = json.loads(config.read_text())
    del data["scenes"][0]["id"]
    dump(config, data)
    with pytest.raises(ValueError, match="stable id"):
        stage(project)
    data["scenes"] = [{"id": "same"}, {"id": "same"}]
    dump(config, data)
    with pytest.raises(ValueError, match="Duplicate scene"):
        stage(project)


def test_old_comments_never_rebase_and_completion_needs_changed_new_version(project, clips):
    first = publish_first(project, clips)
    root, config, _ = project
    item = review.comment(root, revision_id=first["id"], time=.25, text="这个镜头换成蓝色", region=[.1,.2,.2,.2])
    assert item["scene_id"] == "hero" and item["frame"] == 3
    with pytest.raises(ValueError, match="changed newer"):
        review.resolve(root, item["id"], first["id"], "未生成新版")
    config.write_text(config.read_text().replace("真实预览", "真实预览第二版"))
    draft, video, timeline = stage(project, "second")
    produce(video, timeline, clips[1])
    second = review.publish(root, draft["id"])
    # An older frame can still be annotated after another revision was published.
    old = review.comment(root, revision_id=first["id"], time=.5, text="旧版画面上的意见")
    assert old["revision"] == first["id"] and old["video_sha256"] == first["video"]["sha256"]
    review.resolve(root, item["id"], second["id"], "已更换镜头")
    items = review.comments(root)
    assert items[0]["status"] == "done" and items[0]["result_revision"] == second["id"]
    assert items[0]["revision"] == first["id"]
    assert items[1]["status"] == "pending"
    claimed = review.comments(root, claim=True)
    assert claimed[0]["id"] == old["id"]
    assert review.comments(root, claim=True) == []


def test_concurrent_claims_get_different_comments(project, clips):
    first = publish_first(project, clips)
    for n in range(2):
        review.comment(project[0], revision_id=first["id"], time=.2, text=f"意见 {n}")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: review.comments(project[0], claim=True), range(2)))
    assert len({r[0]["id"] for r in results}) == 2


@pytest.mark.parametrize("time,region", [(float("nan"), None), (1, None), (-1, None), (.2,[.99,0,.2,.2])])
def test_comment_context_cannot_escape_displayed_video(project, clips, time, region):
    first = publish_first(project, clips)
    with pytest.raises(ValueError):
        review.comment(project[0], revision_id=first["id"], time=time, region=region, text="invalid")
    assert review.comments(project[0]) == []


def test_same_size_media_tamper_and_manifest_tamper_are_rejected(project, clips):
    doc = publish_first(project, clips)
    root = project[0]
    file = root / "revisions" / doc["id"] / "preview.mp4"
    payload = bytearray(file.read_bytes())
    payload[-1] ^= 1
    file.write_bytes(payload)
    with pytest.raises(ValueError, match="checksum"):
        review.verify(root)
    with pytest.raises(ValueError, match="checksum"):
        review.comment(root, revision_id=doc["id"], time=.2, text="bad")
    shutil.copyfile(clips[0], file)
    manifest = file.with_name("manifest.json")
    data = json.loads(manifest.read_text()); data["video"]["frames"] = 999
    dump(manifest, data)
    with pytest.raises(ValueError, match="checksum"):
        review.verify(root)


def test_http_ranges_comments_and_local_write_boundary(project, clips):
    import re
    first = publish_first(project, clips)
    server = create_server(project[0], 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base) as response:
            html = response.read().decode()
        token = re.search(r"const TOKEN='([^']+)'", html)[1]
        url = base + f"/media/{first['id']}.mp4"
        with urlopen(Request(url, headers={"Range":"bytes=0-99"})) as response:
            assert response.status == 206
            assert response.read() == clips[0].read_bytes()[:100]
        with urlopen(Request(url, headers={"Range":"bytes=-17"})) as response:
            assert response.read() == clips[0].read_bytes()[-17:]
        payload = json.dumps({"revision":first["id"],"time":.2,"text":"HTTP 实际批注"}).encode()
        with pytest.raises(HTTPError) as missing_origin:
            urlopen(Request(base + "/api/comments", data=payload, headers={"X-Review-Token":token}))
        assert missing_origin.value.code == 403
        with urlopen(Request(base + "/api/comments", data=payload,
                             headers={"Content-Type":"application/json","X-Review-Token":token,"Origin":base})) as response:
            created = json.load(response)
        assert created["revision"] == first["id"]
        assert review.comments(project[0])[0]["text"] == "HTTP 实际批注"
        with pytest.raises(HTTPError) as outside:
            urlopen(base + "/source/project.json")
        assert outside.value.code == 404
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_codefilm_partial_preview_keeps_global_time_and_declared_sources(project, clips):
    root, config, outputs = project
    entry = config.parent / "index.html"
    entry.write_text('<canvas></canvas>')
    source_timeline = dump(config.parent / "timeline.json", {
        "fps": 12, "frames": 36, "duration": 3,
        "scenes": [{"id": "whole", "start": 0, "end": 1}, {"id": "detail", "start": 1, "end": 3}],
    })
    dump(config, {"schema": "codefilm-v1", "entry": entry.name, "timeline": source_timeline.name,
                  "width": 320, "height": 180, "sources": [entry.name, source_timeline.name]})
    video = outputs / "partial.mp4"
    draft = review.prepare(root, renderer="codefilm", config=config, video=video, width=160, offset=1, duration=1)
    assert draft["expected"] == {"width": 160, "height": 90, "fps": 12, "offset": 1, "duration": 1}
    assert {str(entry), str(source_timeline), str(config)} <= {r["path"] for r in draft["sources"]}
    outputs.mkdir()
    shutil.copyfile(clips[0], video)
    doc = review.publish(root, draft["id"])
    assert doc["offset"] == 1 and len(doc["scenes"]) == 1
    assert doc["scenes"][0]["id"] == "detail"
    assert (doc["scenes"][0]["start"], doc["scenes"][0]["end"]) == (0, 1)
    item = review.comment(root, revision_id=doc["id"], time=.25, text="局部细节")
    assert item["global_time"] == 1.25 and item["scene_id"] == "detail" and item["frame"] == 3
    entry.write_text('<canvas>edited source</canvas>')
    assert review.state(root)["changed_sources"] == [str(entry)]
