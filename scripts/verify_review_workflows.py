"""Actual photo montage + optional local Taiji review/change/publish smoke.

No downloads or model calls. Models/Chromium remain an optional local smoke,
separate from pytest's small deterministic HTTP/FFmpeg fixtures.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from videocut import review
from videocut.codefilm import main as codefilm
from videocut.codefilm import verify_manifest
from videocut.ffmpeg_tools import invoke_json
from videocut.media import write_json
from videocut.render import render_backgrounds

ROOT = Path(__file__).resolve().parents[1]


def complete(root, first, source_config, generate, change, text, expected_scene, time):
    item = review.comment(root, revision_id=first["id"], time=time, text=text)
    assert item["scene_id"] == expected_scene
    claimed = review.comments(root, claim=True)
    assert claimed[0]["id"] == item["id"]
    change(source_config)
    assert review.state(root)["changed_sources"]
    second = generate("v2")
    assert first["video"]["sha256"] != second["video"]["sha256"]
    assert first["source_hash"] != second["source_hash"]
    assert item["scene_id"] in {s["id"] for s in second["scenes"]}
    review.resolve(root, item["id"], second["id"], text.replace("验收意见：", "已完成："))
    checked = review.verify(root)
    return {"workspace": str(root), "first": first["id"], "second": second["id"],
            "comment": item["id"], "scene_id": item["scene_id"], "verified": checked,
            "videos": [str(root / "revisions" / d["id"] / "preview.mp4") for d in (first, second)]}


def photos(output: Path, paths: list[Path]) -> dict:
    source = output / "sources/photos"
    source.mkdir(parents=True)
    known = json.loads((ROOT / "examples/materials.json").read_text())
    catalog = []
    for n, path in enumerate(paths):
        target = source / f"photo-{n}{path.suffix}"
        shutil.copy2(path, target)
        attribution = next((a for a in known if a.get("filename") == path.name), {})
        catalog.append({"id": f"photo-{n}", "kind": "image", "path": str(target),
                        "original_path": str(path.resolve()), "tags": [],
                        "credit": attribution.get("credit", "User-provided local smoke input"),
                        "license": attribution.get("license", "unspecified"), "page": attribution.get("page")})
    materials = source / "materials.json"
    write_json(materials, catalog)
    config = source / "project.json"
    scenes = [{"id": f"photo-scene-{i+1}", "label": f"咖啡照片 {i+1}", "kind": "image",
               "material_id": catalog[i % len(catalog)]["id"], "start": i*2, "duration": 2,
               "transition": "fade"} for i in range(3)]
    write_json(config, {"title": "图片混剪审片实测", "width": 640, "height": 360, "fps": 24,
                        "transition_seconds": .25, "scenes": scenes})
    workspace = output / "reviews/photos"

    def generate(label):
        job = output / "renders/photos" / label
        current = json.loads(config.read_text())
        draft = review.prepare(workspace, renderer="media", config=config, materials=materials,
                               video=job / "background.mp4", timeline=job / "timeline.json",
                               duration=sum(s["duration"] for s in current["scenes"]), label=label)
        job.mkdir(parents=True)
        render_backgrounds(current, current["scenes"], catalog, job)
        return review.publish(workspace, draft["id"])

    def change(path):
        current = json.loads(path.read_text())
        current["scenes"][1]["duration"] = 3
        current["scenes"][2]["start"] = 5
        write_json(path, current)

    first = generate("v1")
    result = complete(workspace, first, config, generate, change,
                      "验收意见：第二张照片多停留一秒，第三张顺延，保留原镜头 ID。", "photo-scene-2", 2.5)
    latest = review.revision(workspace, result["second"])
    assert latest["video"]["frames"] == 168 and latest["video"]["duration"] == 7
    assert latest["scenes"][1]["end"] - latest["scenes"][1]["start"] == 3
    return result


def taiji(output: Path, original: Path, browser: str | None) -> dict:
    source = output / "sources/taiji"
    source.mkdir(parents=True)
    for name in ("realistic.html", "realistic.js", "character-v2.js", "realistic-codefilm.json", "realistic-timeline.json", "package.json", "package-lock.json", "CREDITS-V2.md"):
        shutil.copy2(original / name, source / name)
    for name in ("models", "fonts", "node_modules/three", "node_modules/playwright-core"):
        shutil.copytree(original / name, source / name)
    config = source / "realistic-codefilm.json"
    workspace = output / "reviews/taiji"

    def generate(label):
        job = output / "renders/taiji" / label
        draft = review.prepare(workspace, renderer="codefilm", config=config,
                               video=job / "preview.mp4", width=640, offset=24, duration=2, label=label)
        arguments = ["render", "--config", str(config), "--output", str(job), "--width", "640",
                     "--start", "24", "--end", "26", "--workers", "1"]
        if browser:
            arguments += ["--browser", browser]
        assert codefilm(arguments) == 0
        path = job / "render-manifest.json"
        checked = verify_manifest(path, allow_partial=True)
        assert not checked["complete"]
        manifest = json.loads(path.read_text())
        # 48 frames fit one native 96-frame chunk, so no second encoder is needed.
        assert len(manifest["chunks"]) == 1 and manifest["frames"] == 48
        shutil.copyfile(manifest["chunks"][0]["file"], job / "preview.mp4")
        return review.publish(workspace, draft["id"])

    def change(_config):
        js = source / "realistic.js"
        text = js.read_text()
        needle = "camera.fov=lerp(a[3],b[3],u);"
        assert text.count(needle) == 1
        js.write_text(text.replace(needle, "camera.fov=lerp(a[3],b[3],u)*.90;"))

    first = generate("v1")
    result = complete(workspace, first, config, generate, change,
                      "验收意见：腿部肌群镜头拉近，保持动作、时序和标注。", "06-muscle-winding-and-tension", .5)
    latest = review.revision(workspace, result["second"])
    assert latest["offset"] == 24 and latest["video"]["frames"] == 48
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--photos", nargs="+", type=Path, default=[ROOT / "assets/cache/coffee-photo.jpg", ROOT / "assets/cache/coffee-desk.jpg"])
    parser.add_argument("--taiji", type=Path, help="Optional local Taiji source with model assets and npm dependencies")
    parser.add_argument("--browser")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = {"photos": photos(output, args.photos)}
    if args.taiji:
        results["taiji"] = taiji(output, args.taiji.resolve(), args.browser)
    for name, result in results.items():
        out = output / (name + "-contact-sheet.png")
        invoke_json(["look", result["videos"][1], "--tiles", "3x2", "--width", "1600", "-o", str(out), "--json"], report=output / (name + "-look.json"))
        result["contact_sheet"] = str(out)
    report = {"passed": True, "cases": results, "paid_api_calls": 0,
              "notes": ["Photo case is a complete silent image montage preview.",
                        "Taiji case, if requested, is explicitly a silent 24–26s partial preview; it is not a full delivery or Qwen validation."]}
    write_json(output / "review-workflows-verification.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
