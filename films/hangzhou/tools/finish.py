"""Join verified frame chunks, master audio, export and inspect the final film.

All FFmpeg operations go through the repository's pinned videocut ffmpeg
interface. The picture's bilingual captions are already drawn in Canvas.
"""
from __future__ import annotations

from paths import output_directory

import json
import pathlib
import hashlib

from videocut.codefilm import sha256, verify_manifest
from videocut.ffmpeg_tools import invoke_json

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = None


def call(args, name):
    return invoke_json(list(map(str, args)), report=OUT / name)


def main():
    manifest = json.loads((OUT / "render-manifest.json").read_text())
    timeline = json.loads((OUT / "timeline.json").read_text())
    verify_manifest(OUT / "render-manifest.json")
    if manifest["start_frame"] != 0 or manifest["frames"] != timeline["frames"]:
        raise ValueError("A partial preview cannot be delivered as the full film")

    # Resuming unchanged chunks updates timing metadata, not the film identity.
    render_identity = {k: manifest[k] for k in ("source_hash", "width", "height", "fps", "frames")}
    render_identity["chunks"] = [{k: c[k] for k in ("a", "b", "sha256")} for c in manifest["chunks"]]
    inputs = {"render": hashlib.sha256(json.dumps(render_identity, sort_keys=True).encode()).hexdigest(), "mix": sha256(OUT / "mix.wav"),
              "timeline": sha256(OUT / "timeline.json"), "finish_tool": sha256(pathlib.Path(__file__))}

    def stage(args, name, destination):
        record = destination.with_name(destination.name + ".post.json")
        if destination.exists():
            if not record.exists():
                raise ValueError(f"Existing post artifact has no checked provenance: {destination}; choose a new output")
            previous = json.loads(record.read_text())
            if previous["inputs"] != inputs or previous["sha256"] != sha256(destination):
                raise ValueError(f"Post inputs or artifact changed: {destination}; choose a new output")
            return
        call([*args, "--dry-run", "--json"], name + "-plan.json")
        call([*args, "--json"], name + "-result.json")
        record.write_text(json.dumps({"inputs": inputs, "sha256": sha256(destination)}, indent=2))

    final = OUT / "杭州-一城山水千年生长.mp4"
    candidate = OUT / "export-before-chapters.mp4"
    project = {
        "output": str(candidate),
        "clips": [{"src": c["file"]} for c in manifest["chunks"]],
        "transition": {"type": "none"},
        "audio": {"replace": str(OUT / "mix.wav"), "stereo": True},
        "loudness": {"lufs": -14, "tp": -1.8},
        "export": {"preset": "copy"},
        "check": {"platform": "youtube", "content": True}
    }
    project_path = OUT / "post-project.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2))
    stage(["render", project_path, "--timeout", "1800"], "post", candidate)
    candidate_probe = call(["probe", candidate, "--json"], "export-probe.json")
    if candidate_probe["video"]["nb_frames"] != timeline["frames"]:
        raise ValueError("The export candidate is incomplete")
    # Give AAC encoding a little peak margin; this pass preserves video bits.
    master = OUT / "master-before-chapters.mp4"
    args = ["loudness", candidate, "-I", "-14", "--tp", "-1.8", "-o", master]
    stage(args, "master", master)
    chapter_file = OUT / "chapters.txt"
    chapter_file.write_text("\n".join(f"{s['start']:.3f} {s['title']}" for s in timeline["scenes"]) + "\n")
    args = ["metadata", master, "--chapters", chapter_file, "-o", final]
    stage(args, "chapters", final)
    probe = call(["probe", final, "--json"], "final-probe.json")
    v, a = probe["video"], probe["audio"]
    if (v["width"], v["height"], v["fps"], v["nb_frames"]) != (1920, 1080, 24, timeline["frames"]):
        raise ValueError("The delivered video does not match the full frame manifest")
    if v["pix_fmt"] != "yuv420p" or not a or a["channels"] != 2:
        raise ValueError("The delivered video is not H.264 4:2:0 with stereo audio")
    call(["look", final, "--tiles", "4x3", "--width", "2560", "-o", OUT / "contact-sheet.png", "--overwrite", "--json-brief"], "final-look.json")
    scenes = timeline["scenes"]
    selected = sorted({round(i * (len(scenes) - 1) / 4) for i in range(5)})
    args = ["look", final, "-o", OUT / "final-keyframe.png", "--overwrite", "--json-brief"]
    for index in selected:
        scene = scenes[index]
        at = min(timeline["duration"] - 1 / manifest["fps"], scene["start"] + (scene["end"] - scene["start"]) * .52)
        args += ["--at", f"{at:.3f}"]
    call(args, "final-keyframes.json")
    checks = call(["check", final, "--platform", "youtube", "--content", "--json"], "final-check.json")
    if not checks["ok"]:
        raise ValueError("The platform/content checks failed; inspect final-check.json")
    print(final, flush=True)


if __name__ == "__main__":
    OUT = output_directory(protect_delivery=False)
    main()
