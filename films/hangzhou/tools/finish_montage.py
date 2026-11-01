"""Splice native montage shots into the original film without moving speech.

The montage renderer uses a compact timeline containing cutaways only. This
script expands it back to the original frame positions, checks every encoded
chunk, and leaves the original delivery unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from videocut.codefilm import plan, verify_manifest
from videocut.ffmpeg_tools import invoke_json

FILM = Path(__file__).resolve().parents[1]


def frame(seconds: float) -> int:
    value = round(seconds * 24)
    if abs(seconds * 24 - value) > 1e-6:
        raise ValueError(f"Time is not on a video frame: {seconds}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", type=Path, required=True, help="Complete compact codefilm render directory")
    parser.add_argument("--base", type=Path, required=True, help="Original full film, matching data/timeline.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.plan_only and shutil.disk_usage(out).free < 2_000_000_000:
        raise ValueError("Full montage assembly needs at least 2 GB free for disposable containers; plan-only remains available")
    base = args.base.resolve()
    timeline = json.loads((FILM / "data/timeline.json").read_text())
    edit = json.loads((FILM / "montage-edit.json").read_text())
    render = args.render.resolve() / "render-manifest.json"
    verify_manifest(render)
    manifest = json.loads(render.read_text())
    if (manifest["frames"], manifest["width"], manifest["height"], manifest["fps"]) != (edit["frames"], 1920, 1080, 24):
        raise ValueError("Only a complete 1080p compact render can be assembled")
    if manifest["source_hash"] != plan(FILM / "montage-codefilm.json")["source_hash"]:
        raise ValueError("Render source no longer matches the current edit")
    probe = invoke_json(["probe", str(base), "--json"], report=out / "base-probe.json")
    v = probe["video"]
    if (v["width"], v["height"], v["fps"], v["nb_frames"]) != (1920, 1080, 24, timeline["frames"]):
        raise ValueError("Original movie does not match the narration timeline")
    base_digest = hashlib.file_digest(base.open("rb"), "sha256").hexdigest()
    if base_digest != edit["base_video_sha256"]:
        raise ValueError("Original film differs from the reviewed narration and subtitles")
    clips, coverage = [], []
    cutaway_projects = []
    cursor = 0
    for shot in edit["shots"]:
        a, b = frame(shot["at"]), frame(shot["until"])
        if not (cursor <= a < b <= timeline["frames"]):
            raise ValueError("Cutaways overlap or escape the original film")
        if a > cursor:
            clips.append({"src": str(base), "in": cursor / 24, "out": a / 24})
            coverage.append({"a": cursor, "b": a, "kind": "original"})
        first, last = frame(shot["start"]), frame(shot["end"])
        position = first
        shot_clips = []
        for chunk in manifest["chunks"]:
            x, y = max(first, chunk["a"]), min(last, chunk["b"])
            if x >= y:
                continue
            if x != position:
                raise ValueError("A cutaway has missing encoded frames")
            clip = {"src": chunk["file"]}
            if (x, y) != (chunk["a"], chunk["b"]):
                clip.update({"in": (x - chunk["a"]) / 24, "out": (y - chunk["a"]) / 24})
            shot_clips.append(clip)
            position = y
        if position != last or last - first != b - a:
            raise ValueError("Cutaway duration differs from its original window")
        # Keep the final join's decoder count bounded. A 1-second capture cache
        # otherwise supplies ~100 video inputs plus as many silence generators.
        shot_file = out / "cutaways" / f"{shot['id']}.mp4"
        shot_project = {"output": str(shot_file), "clips": shot_clips,
                        "transition": {"type": "none"}, "export": {"preset": "copy"}}
        cutaway_projects.append((shot_project, b - a))
        clips.append({"src": str(shot_file)})
        coverage.append({"a": a, "b": b, "kind": shot["asset"], "compact_a": first, "compact_b": last})
        cursor = b
    if cursor < timeline["frames"]:
        clips.append({"src": str(base), "in": cursor / 24, "out": timeline["frames"] / 24})
        coverage.append({"a": cursor, "b": timeline["frames"], "kind": "original"})
    if sum(s["b"] - s["a"] for s in coverage) != timeline["frames"]:
        raise ValueError("The final timeline is incomplete")
    final = out / "杭州-山水与城市-实景混剪.mp4"
    if final.exists():
        raise ValueError("Final already exists; use a new output directory")
    project = {"output": str(final), "clips": clips, "transition": {"type": "none"},
               "audio": {"replace": str(base), "stereo": True}, "export": {"preset": "copy"},
               "chapters": [{"at": s["start"], "title": s["title"]} for s in timeline["scenes"]],
               "check": {"platform": "youtube", "content": True}}
    project_path = out / "montage-project.json"
    project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n")
    (out / "edit-coverage.json").write_text(json.dumps({"base": str(base), "base_sha256": base_digest,
        "frames": timeline["frames"], "source_hash": manifest["source_hash"], "coverage": coverage}, ensure_ascii=False, indent=2) + "\n")
    (out / "cutaways").mkdir(exist_ok=True)
    for index, (shot_project, count) in enumerate(cutaway_projects):
        shot_file = Path(shot_project["output"])
        shot_path = shot_file.with_suffix(".project.json")
        record_path = shot_file.with_suffix(".record.json")
        cache_inputs = {
            "source_hash": manifest["source_hash"],
            "project": shot_project,
            "finish_tool_sha256": hashlib.file_digest(Path(__file__).open("rb"), "sha256").hexdigest(),
        }
        shot_path.write_text(json.dumps(shot_project, ensure_ascii=False, indent=2) + "\n")
        if args.plan_only:
            invoke_json(["render", str(shot_path), "--dry-run", "--json"], report=shot_file.with_suffix(".plan.json"))
            continue
        if shot_file.exists():
            if not record_path.exists():
                raise ValueError(f"Unverified cutaway already exists: {shot_file}")
            record = json.loads(record_path.read_text())
            digest = hashlib.file_digest(shot_file.open("rb"), "sha256").hexdigest()
            if record["inputs"] != cache_inputs or record["sha256"] != digest:
                raise ValueError(f"Cutaway or inputs changed: {shot_file}")
        else:
            invoke_json(["render", str(shot_path), "--dry-run", "--json"], report=shot_file.with_suffix(".plan.json"))
            invoke_json(["render", str(shot_path), "--json"], report=shot_file.with_suffix(".result.json"))
            digest = hashlib.file_digest(shot_file.open("rb"), "sha256").hexdigest()
            record_path.write_text(json.dumps({"inputs": cache_inputs, "sha256": digest}, indent=2))
        actual = invoke_json(["probe", str(shot_file), "--json"], report=shot_file.with_suffix(".probe.json"))
        expected = {"nb_frames": count, "width": 1920, "height": 1080, "fps": 24,
                    "codec": "h264", "pix_fmt": "yuv420p", "color_range": "tv"}
        if any(actual["video"].get(key) != value for key, value in expected.items()):
            raise ValueError(f"Cutaway video changed: {shot_file}")
        print(f"CUTAWAY {index + 1}/{len(cutaway_projects)} {shot_file.name}", flush=True)
    if args.plan_only:
        (out / "post-plan-pending.json").write_text(json.dumps({
            "status": "pending_cutaways", "project": str(project_path),
            "note": "Each cutaway has a real FFmpeg dry run; the final dry run follows after their files exist.",
        }, indent=2) + "\n")
        return
    invoke_json(["render", str(project_path), "--dry-run", "--json"], report=out / "post-plan.json")
    invoke_json(["render", str(project_path), "--json", "--timeout", "1800"], report=out / "post-result.json")
    actual = invoke_json(["probe", str(final), "--json"], report=out / "final-probe.json")
    if (actual["video"]["nb_frames"], actual["video"]["fps"]) != (timeline["frames"], 24):
        raise ValueError("Final frame count changed during assembly")
    if hashlib.file_digest(base.open("rb"), "sha256").hexdigest() != base_digest:
        raise ValueError("Original film changed during assembly")
    print(final, flush=True)


if __name__ == "__main__":
    main()
