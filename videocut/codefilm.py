"""Deterministic browser frames -> checked FFmpeg segments.

This module owns rendering infrastructure, not a city's GIS data or story.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .ffmpeg_tools import invoke_json, skill_directory

SCHEMA = "codefilm-render-v1"
RUNNER = Path(__file__).with_name("codefilm_runner.mjs")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def inside(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path escapes the film directory: {name}")
    return path


def integer(value, label: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def plan(config_path: Path, *, width: int | None = None) -> dict:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text())
    if config.get("schema") != "codefilm-v1":
        raise ValueError("Expected schema codefilm-v1")
    root = config_path.parent
    entry = inside(root, config.get("entry", "index.html"))
    timeline_path = inside(root, config["timeline"])
    timeline = json.loads(timeline_path.read_text())
    fps = integer(timeline["fps"], "timeline.fps")
    frames = integer(timeline["frames"], "timeline.frames")
    duration = frames / fps
    if not math.isfinite(timeline["duration"]) or abs(timeline["duration"] - duration) > 1e-6:
        raise ValueError("timeline.duration must equal frames / fps")
    scenes = timeline.get("scenes", [])
    for scene in scenes:
        if not (0 <= scene["start"] < scene["end"] <= duration + 1 / fps):
            raise ValueError("Scene times must be inside the timeline")
    base_w = integer(config.get("width", 1920), "width")
    base_h = integer(config.get("height", 1080), "height")
    w = integer(width if width is not None else base_w, "width")
    h = round(base_h * w / base_w / 2) * 2 if width is not None else base_h
    if w % 2 or h < 2 or h % 2:
        raise ValueError("H.264 width and height must be positive even numbers")
    chunk_frames = integer(config.get("chunk_frames", 120), "chunk_frames")
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources or any(not isinstance(s, str) for s in sources):
        raise ValueError("sources must list every local rendering input (files or directories)")
    paths = {config_path, entry, timeline_path}
    for name in sources:
        source = inside(root, name)
        if not source.exists():
            raise ValueError(f"Missing source: {source}")
        for path in source.rglob("*") if source.is_dir() else [source]:
            resolved = inside(root, str(path.relative_to(root)))
            if resolved.is_file():
                paths.add(resolved)
    records = [{"path": str(p.relative_to(root)), "sha256": sha256(p)} for p in sorted(paths)]
    # A tool/encoder wrapper change must not silently reuse yesterday's pixels.
    runtime = [Path(__file__), RUNNER, Path(__file__).with_name("ffmpeg_tools.py")]
    runtime += sorted((skill_directory() / "scripts").rglob("*.py"))
    tool_hash = hashlib.sha256("".join(sha256(p) for p in runtime).encode()).hexdigest()
    settings = {"width": w, "height": h, "fps": fps, "total_frames": frames, "chunk_frames": chunk_frames}
    identity = {"sources": records, "settings": settings, "toolchain_sha256": tool_hash}
    source_hash = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return {
        "schema": SCHEMA, "config": str(config_path), "root": str(root),
        "entry": str(entry.relative_to(root)), "timeline": str(timeline_path),
        **settings, "duration": duration, "scenes": scenes,
        **identity, "source_hash": source_hash,
    }


def check_video(probe: dict, manifest: dict, frames: int) -> None:
    v = probe.get("video") or {}
    expected = {
        "width": manifest["width"], "height": manifest["height"],
        "fps": manifest["fps"], "nb_frames": frames,
        "codec": "h264", "pix_fmt": "yuv420p", "color_range": "tv",
    }
    for key, value in expected.items():
        if v.get(key) != value:
            raise ValueError(f"Encoded video {key}: expected {value}, got {v.get(key)}")


def verify_manifest(path: Path, *, video: Path | None = None, allow_partial: bool = False) -> dict:
    path = path.resolve()
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported render manifest; render with videocut codefilm first")
    start, end, total = (integer(manifest[k], k, 0) for k in ("start_frame", "end_frame", "total_frames"))
    if not (0 <= start < end <= total) or manifest["frames"] != end - start:
        raise ValueError("Invalid manifest frame interval")
    complete = start == 0 and end == total
    if not complete and not allow_partial:
        raise ValueError("A partial render cannot be delivered as the full film; use --allow-partial for a preview")
    expected = start
    chunks = manifest["chunks"]
    if not chunks:
        raise ValueError("The render manifest contains no chunks")
    for chunk in chunks:
        a, b = integer(chunk["a"], "chunk.a", 0), integer(chunk["b"], "chunk.b")
        if a != expected or not a < b <= end:
            raise ValueError("The rendered timeline has a gap, duplicate or invalid chunk")
        file = Path(chunk["file"])
        if not file.is_absolute():
            file = path.parent / file
        if sha256(file) != chunk["sha256"]:
            raise ValueError(f"Cached segment checksum mismatch: {file}")
        # Re-probe actual bytes; an old sidecar is not evidence of today's file.
        check_video(invoke_json(["probe", str(file), "--json"]), manifest, b - a)
        expected = b
    if expected != end:
        raise ValueError("The full requested time range was not rendered")
    result = {
        "schema": "codefilm-verification-v1", "passed": True,
        "manifest": str(path), "source_hash": manifest["source_hash"],
        "complete": complete, "frames": end - start, "chunks": len(chunks),
        "subtitle_sync": {"passed": None, "reason": "Frame integrity is not Qwen/sync.py subtitle acceptance"},
    }
    if video:
        check_video(invoke_json(["probe", str(video.resolve()), "--json"]), manifest, end - start)
        result["video"] = {"file": str(video.resolve()), "sha256": sha256(video)}
    return result


@contextlib.contextmanager
def output_lock(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".codefilm.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"Another codefilm render is writing {output}") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videocut codefilm", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "render", "stills"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--width", type=int)
        if name != "plan":
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--browser", help="Chromium executable; otherwise PLAYWRIGHT_CHROME or Playwright default")
            command.add_argument("--angle", default=os.environ.get("LEMO_ANGLE", "metal" if sys.platform == "darwin" else "default"))
            command.add_argument("--timeout", type=float, default=120, help="Per-page/frame timeout in seconds")
            if name == "render":
                command.add_argument("--start", type=float, default=0)
                command.add_argument("--end", type=float)
                command.add_argument("--workers", type=int, default=2)
    command = commands.add_parser("verify")
    command.add_argument("manifest", type=Path)
    command.add_argument("--video", type=Path)
    command.add_argument("--allow-partial", action="store_true")
    command.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            if args.report and args.report.resolve() in {args.manifest.resolve(), args.video.resolve() if args.video else None}:
                raise ValueError("Report must not overwrite an input")
            report = verify_manifest(args.manifest, video=args.video, allow_partial=args.allow_partial)
            if args.report:
                write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        request = plan(args.config, width=args.width)
        if args.command == "plan":
            print(json.dumps(request, ensure_ascii=False, indent=2))
            return 0
        start = getattr(args, "start", 0)
        end = getattr(args, "end", None)
        end = request["duration"] if end is None else end
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= request["duration"]):
            raise ValueError("Require 0 <= start < end <= timeline.duration")
        a, b = round(start * request["fps"]), round(end * request["fps"])
        if a == b:
            raise ValueError("Requested interval contains no frames")
        workers = integer(getattr(args, "workers", 1), "workers")
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be positive")
        if not shutil.which("node"):
            raise ValueError("Node.js 20+ is required")
        output = args.output.resolve()
        root = Path(request["root"])
        if output.is_relative_to(root) or root.is_relative_to(output):
            raise ValueError("Output and film source directories must be separate")
        request.update({"mode": args.command, "output": str(output), "python": sys.executable,
                        "browser": args.browser or os.environ.get("PLAYWRIGHT_CHROME"), "angle": args.angle,
                        "timeout_ms": args.timeout * 1000, "workers": workers, "start_frame": a, "end_frame": b})
        with output_lock(output):
            request_path = output / "codefilm-request.json"
            write_json(request_path, request)
            result = subprocess.run(["node", str(RUNNER), str(request_path)], check=False)
            if result.returncode:
                return result.returncode
            if plan(args.config, width=args.width)["source_hash"] != request["source_hash"]:
                raise ValueError("Rendering inputs changed during capture; rerun before delivery")
            name = "latest-stills" if args.command == "stills" else "render-manifest"
            (output / f"{name}.pending.json").replace(output / f"{name}.json")
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"codefilm: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
