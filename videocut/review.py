"""Local, immutable preview revisions and version-bound review comments.

Renderers keep their own timelines. A draft records declared inputs before a
render; publishing seals the actual encoded artifact only while those inputs
still match. This module does not generate speech, align captions or judge art.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import uuid
from fractions import Fraction
from pathlib import Path

from .media import probe, run

SCHEMA = "videocut-review-v1"
_IDENTITY = re.compile(r"^[0-9a-f]{16}$")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")  # noqa: TRY004 - invalid JSON value, reported as input validation
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def _lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".review.lock").open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _state(root: Path) -> dict:
    state = _json(root / "review.json")
    if state.get("schema") != SCHEMA:
        raise ValueError("Unsupported review schema")
    return state


def _identity(value: str) -> str:
    if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
        raise ValueError("Invalid review identity")
    return value


def _number(value: object, name: str, *, minimum: float = 0) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be a finite number >= {minimum}")
    return float(value)


def _scene_ids(scenes: object) -> list[str]:
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Review requires scenes with stable explicit id values")
    ids = []
    for scene in scenes:
        key = scene.get("id") if isinstance(scene, dict) else None
        if not isinstance(key, str) or not key.strip() or len(key) > 128:
            raise ValueError("Every reviewed scene needs an explicit stable id; preserve it when editing/reordering")
        if key in ids:
            raise ValueError(f"Duplicate scene id: {key}")
        ids.append(key)
    return ids


def _fingerprints(paths: list[Path]) -> list[dict]:
    files: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if not path.exists():
            raise ValueError(f"Missing declared review input: {path}")
        if path.is_dir():
            files.update(p.resolve() for p in path.rglob("*") if p.is_file())
        else:
            files.add(path)
    return [{"path": str(p), "sha256": digest(p), "bytes": p.stat().st_size} for p in sorted(files)]


def _source_hash(records: list[dict]) -> str:
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def changed_sources(records: list[dict]) -> list[str]:
    return [r["path"] for r in records if not Path(r["path"]).is_file() or digest(Path(r["path"])) != r["sha256"]]


def prepare(
    root: Path, *, renderer: str, config: Path, video: Path,
    timeline: Path | None = None, materials: Path | None = None,
    sources: list[Path] | None = None, label: str = "预览",
    width: int | None = None, height: int | None = None,
    offset: float = 0, duration: float | None = None,
) -> dict:
    """Register inputs BEFORE generating a new candidate. Never modifies sources."""
    root, config, video = root.resolve(), config.resolve(), video.resolve()
    if renderer not in {"media", "codefilm"}:
        raise ValueError("renderer must be media or codefilm")
    if video.exists():
        raise ValueError("Candidate video already exists; register a fresh output before rendering")
    if root == config.parent or root in config.parents:
        raise ValueError("Editable sources must be outside the review workspace")
    document = _json(config)
    paths = [config, *(sources or [])]
    offset = _number(offset, "offset")
    if renderer == "codefilm":
        from .codefilm import plan
        planned = plan(config, width=width)
        paths += [config.parent / r["path"] for r in planned["sources"]]
        scenes = planned["scenes"]
        fps = planned["fps"]
        width, height = width or planned["width"], height or planned["height"]
        timeline = timeline or Path(planned["timeline"])
        duration = planned["duration"] - offset if duration is None else duration
        if offset + _number(duration, "duration", minimum=.000001) > planned["duration"] + 1e-6:
            raise ValueError("Preview interval exceeds codefilm timeline")
    else:
        scenes, fps = document.get("scenes"), document.get("fps")
        width, height = width or document.get("width"), height or document.get("height")
        if materials:
            materials = materials.resolve()
            paths.append(materials)
            catalog = json.loads(materials.read_text())
            if not isinstance(catalog, list):
                raise ValueError("Use a local resolved materials list")
            for item in catalog:
                if not isinstance(item, dict) or not item.get("path"):
                    raise ValueError("Review material inputs need local path values; resolve/download assets first")
                item_path = Path(item["path"])
                paths.append(item_path if item_path.is_absolute() else materials.parent / item_path)
        if timeline is None:
            raise ValueError("Media review requires the renderer's timeline output path")
    ids = _scene_ids(scenes)
    fps = _number(fps, "fps", minimum=.000001)
    if any(type(n) is not int or n <= 0 or n % 2 for n in (width, height)):
        raise ValueError("Preview width and height must be positive even integers")
    if duration is not None:
        duration = _number(duration, "duration", minimum=1 / fps)
        if abs(duration * fps - round(duration * fps)) > 1e-6:
            raise ValueError("Preview duration must contain an integer number of frames")
    records = _fingerprints(paths)
    if str(video) in {r["path"] for r in records}:
        raise ValueError("Candidate cannot also be a source input")
    with _lock(root):
        if (root / "review.json").exists():
            state = _state(root)
        else:
            state = {"schema": SCHEMA, "project_id": uuid.uuid4().hex, "revisions": [], "latest": None, "pending": None}
        if state["pending"]:
            raise ValueError("A draft is pending; publish or explicitly abandon it first")
        draft = {
            "schema": SCHEMA, "id": uuid.uuid4().hex[:16], "created": _now(), "status": "pending",
            "renderer": renderer, "label": label, "config": str(config), "config_snapshot": document,
            "candidate": str(video), "timeline": str(timeline.resolve()),
            "sources": records, "source_hash": _source_hash(records), "scene_ids": ids,
            "expected": {"width": width, "height": height, "fps": fps, "duration": duration, "offset": offset},
        }
        _write(root / "drafts" / (draft["id"] + ".json"), draft)
        state["pending"] = draft["id"]
        _write(root / "review.json", state)
        return draft


def inspect_video(path: Path) -> dict:
    """Count decoded frames and reject decode errors, not just stream metadata."""
    measured = probe(path)
    videos = [s for s in measured["streams"] if s["codec_type"] == "video"]
    if len(videos) != 1:
        raise ValueError("Review preview must contain exactly one video stream")
    stream = videos[0]
    try:
        fps = float(Fraction(stream["avg_frame_rate"]))
        nominal = float(Fraction(stream["r_frame_rate"]))
    except (ValueError, ZeroDivisionError, KeyError) as error:
        raise ValueError("Invalid preview frame rate") from error
    if fps <= 0 or abs(fps - nominal) > 1e-6:
        raise ValueError("Review requires constant frame rate video")
    count = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                 "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)])
    # H.264 side-data can add an empty CSV column even when only one stream
    # field was requested (e.g. "144,\n"). Parse the structured stream record.
    streams = json.loads(count.stdout).get("streams", [])
    frames = streams[0].get("nb_read_frames", "") if len(streams) == 1 else ""
    if count.stderr.strip() or not str(frames).isdigit() or int(frames) <= 0:
        raise ValueError("Could not decode and count preview frames")
    run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"])
    frames = int(frames)
    return {"sha256": digest(path), "bytes": path.stat().st_size, "width": stream["width"],
            "height": stream["height"], "fps": fps, "frames": frames, "duration": frames / fps,
            "codec": stream["codec_name"], "audio": [s["codec_name"] for s in measured["streams"] if s["codec_type"] == "audio"]}


def _timeline(raw: dict, draft: dict, video: dict) -> list[dict]:
    _scene_ids(raw.get("scenes"))
    offset, end = draft["expected"]["offset"], draft["expected"]["offset"] + video["duration"]
    scenes = []
    for scene in raw["scenes"]:
        if scene["id"] not in draft["scene_ids"]:
            raise ValueError(f"Rendered timeline has an unknown scene id: {scene['id']}")
        start = _number(scene.get("start"), "scene.start")
        finish = scene.get("end")
        finish = _number(finish if finish is not None else start + _number(scene.get("duration"), "scene.duration", minimum=.000001), "scene.end")
        if finish <= start:
            raise ValueError("Invalid rendered scene interval")
        a, b = max(start, offset), min(finish, end)
        if b <= a:
            continue
        material = scene.get("material", {})
        scenes.append({"id": scene["id"], "label": scene.get("label", scene["id"]),
                       "start": a - offset, "end": b - offset, "source_start": start, "source_end": finish,
                       "material_id": material.get("id", scene.get("material_id")),
                       "material_path": material.get("path")})
    scenes.sort(key=lambda s: s["start"])
    covered = 0.0
    for scene in scenes:
        if scene["start"] > covered + 1 / video["fps"]:
            raise ValueError("Rendered timeline has a gap in the preview")
        covered = max(covered, scene["end"])
    if covered < video["duration"] - 1 / video["fps"]:
        raise ValueError("Rendered timeline does not cover the preview")
    return scenes


def publish(root: Path, draft_id: str | None = None) -> dict:
    root = root.resolve()
    with _lock(root):
        state = _state(root)
        key = _identity(draft_id or state["pending"] or "")
        draft_path = root / "drafts" / (key + ".json")
        draft = _json(draft_path)
        if state["pending"] != key or draft["status"] != "pending":
            raise ValueError("Draft is no longer pending")
        if changed_sources(draft["sources"]):
            raise ValueError("Source inputs changed after draft registration; prepare and render a new draft")
        candidate = Path(draft["candidate"])
        info = inspect_video(candidate)
        expected = draft["expected"]
        for field in ("width", "height", "fps"):
            if abs(info[field] - expected[field]) > 1e-6:
                raise ValueError(f"Preview {field} differs from the registered draft")
        if expected["duration"] is not None and info["frames"] != round(expected["duration"] * expected["fps"]):
            raise ValueError("Preview frame count differs from the registered duration")
        scenes = _timeline(_json(Path(draft["timeline"])), draft, info)
        revision = uuid.uuid4().hex[:16]
        directory = root / "revisions" / (revision + ".pending")
        directory.mkdir(parents=True)
        shutil.copyfile(candidate, directory / "preview.mp4")
        if digest(directory / "preview.mp4") != info["sha256"] or digest(candidate) != info["sha256"]:
            raise ValueError("Preview changed while being published")
        if changed_sources(draft["sources"]):
            raise ValueError("Source inputs changed while publishing")
        manifest = {
            "schema": SCHEMA, "id": revision, "number": len(state["revisions"]) + 1,
            "parent": state["latest"], "created": _now(), "label": draft["label"], "draft_id": key,
            "renderer": draft["renderer"], "config": draft["config"], "config_snapshot": draft["config_snapshot"],
            "sources": draft["sources"], "source_hash": draft["source_hash"], "offset": expected["offset"],
            "video": info, "scenes": scenes,
            "checks": {"integrity": {"passed": True, "decoded_frames": info["frames"]},
                       "subtitle_sync": {"passed": None, "reason": "Review publishing does not run Qwen or sync.py"},
                       "content": {"passed": None}, "aesthetic": {"passed": None}},
        }
        _write(directory / "manifest.json", manifest)
        sealed_hash = digest(directory / "manifest.json")
        os.replace(directory, root / "revisions" / revision)
        state["revisions"].append({"id": revision, "manifest_sha256": sealed_hash})
        state.update(latest=revision, pending=None)
        _write(root / "review.json", state)
        draft.update(status="published", revision=revision)
        _write(draft_path, draft)
        return manifest


def abandon(root: Path) -> None:
    root = root.resolve()
    with _lock(root):
        state = _state(root)
        if state["pending"]:
            path = root / "drafts" / (state["pending"] + ".json")
            draft = _json(path)
            draft["status"] = "abandoned"
            _write(path, draft)
            state["pending"] = None
            _write(root / "review.json", state)


def revision(root: Path, key: str, *, media: bool = False) -> dict:
    key = _identity(key)
    state = _state(root)
    record = next((r for r in state["revisions"] if r["id"] == key), None)
    path = root / "revisions" / key / "manifest.json"
    if record is None or digest(path) != record["manifest_sha256"]:
        raise ValueError("Revision manifest checksum mismatch or unknown revision")
    doc = _json(path)
    if media and digest(root / "revisions" / key / "preview.mp4") != doc["video"]["sha256"]:
        raise ValueError("Revision video checksum mismatch")
    return doc


def _events(root: Path) -> list[dict]:
    path = root / "comments.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _append(root: Path, event: dict) -> None:
    with (root / "comments.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**event, "at": _now()}, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _comments(root: Path) -> list[dict]:
    items = {}
    for e in _events(root):
        if e["type"] == "comment":
            items[e["id"]] = {**e, "status": "pending"}
        elif e["id"] in items:
            items[e["id"]].update({k: v for k, v in e.items() if k not in {"type", "id", "at"}})
    return list(items.values())


def comment(root: Path, *, revision_id: str, time: float, text: str, scene_id: str | None = None,
            region: list[float] | None = None) -> dict:
    root = root.resolve()
    if not isinstance(text, str) or not text.strip() or len(text) > 8000:
        raise ValueError("Comment text must contain 1–8000 characters")
    with _lock(root):
        doc = revision(root, revision_id, media=True)
        time = _number(time, "time")
        if time >= doc["video"]["duration"]:
            raise ValueError("Comment time must be inside the displayed preview")
        choices = [s for s in doc["scenes"] if s["start"] <= time < s["end"]]
        scene = next((s for s in choices if s["id"] == scene_id), None) if scene_id else choices[-1] if choices else None
        if scene is None:
            raise ValueError("Scene does not match the displayed time/revision")
        if region is not None:
            if not isinstance(region, list) or len(region) != 4:
                raise ValueError("Region must be normalized [x, y, width, height]")
            region = [_number(v, "region") for v in region]
            if region[2] <= 0 or region[3] <= 0 or region[0] + region[2] > 1 or region[1] + region[3] > 1:
                raise ValueError("Region must lie inside the displayed video")
        item = {"type": "comment", "id": uuid.uuid4().hex[:16], "revision": doc["id"],
                "video_sha256": doc["video"]["sha256"], "source_hash": doc["source_hash"],
                "time": time, "global_time": time + doc["offset"], "frame": math.floor(time * doc["video"]["fps"]),
                "scene_id": scene["id"], "region": region, "text": text.strip()}
        _append(root, item)
        return {**item, "status": "pending"}


def comments(root: Path, *, claim: bool = False) -> list[dict]:
    root = root.resolve()
    with _lock(root):
        items = _comments(root)
        if claim:
            pending = next((c for c in items if c["status"] == "pending"), None)
            if pending:
                _append(root, {"type": "status", "id": pending["id"], "status": "working"})
                items = [{**pending, "status": "working"}]
            else:
                items = []
        result = []
        for c in items:
            doc = revision(root, c["revision"])
            result.append({**c, "config": doc["config"], "config_snapshot": doc["config_snapshot"],
                           "sources": doc["sources"], "changed_sources": changed_sources(doc["sources"])})
        return result


def resolve(root: Path, comment_id: str, result_revision: str, note: str) -> dict:
    root = root.resolve()
    if not isinstance(note, str) or not note.strip() or len(note) > 8000:
        raise ValueError("A completion note is required")
    with _lock(root):
        item = next((c for c in _comments(root) if c["id"] == _identity(comment_id)), None)
        if item is None or item["status"] == "done":
            raise ValueError("Unknown or already completed comment")
        result = revision(root, result_revision, media=True)
        original = revision(root, item["revision"])
        if result["number"] <= original["number"] or (result["source_hash"], result["video"]["sha256"]) == (original["source_hash"], original["video"]["sha256"]):
            raise ValueError("Completion requires an actually changed newer preview revision")
        event = {"type": "status", "id": item["id"], "status": "done", "result_revision": result["id"], "note": note.strip()}
        _append(root, event)
        return event


def state(root: Path) -> dict:
    root = root.resolve()
    with _lock(root):
        data = _state(root)
        revisions = [revision(root, r["id"]) for r in data["revisions"]]
        latest = revisions[-1] if revisions else None
        draft = _json(root / "drafts" / (data["pending"] + ".json")) if data["pending"] else None
        return {"schema": SCHEMA, "project_id": data["project_id"], "latest": data["latest"],
                "revisions": revisions, "comments": _comments(root),
                "changed_sources": changed_sources(latest["sources"]) if latest else [],
                "pending": {"id": draft["id"], "label": draft["label"], "changed_sources": changed_sources(draft["sources"])} if draft else None}


def verify(root: Path) -> dict:
    root = root.resolve()
    with _lock(root):
        docs = []
        for record in _state(root)["revisions"]:
            doc = revision(root, record["id"], media=True)
            actual = inspect_video(root / "revisions" / doc["id"] / "preview.mp4")
            if actual != doc["video"]:
                raise ValueError("Revision metadata does not match decoded video")
            docs.append({"revision": doc["id"], "frames": actual["frames"]})
        if not docs:
            raise ValueError("No published preview to verify")
        return {"schema": SCHEMA, "integrity": {"passed": True}, "revisions": docs,
                "subtitle_sync": {"passed": None}, "aesthetic": {"passed": None}}
