"""File handoff from a host agent to the existing renderer; no model calls."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .downloads import inspect_material
from .media import write_json

SCHEMA = "videocut-creation-v1"


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _path(value: str, root: Path) -> Path:
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise ValueError(f"Creation plan schema must be {SCHEMA}")
    project = plan.get("project")
    if not isinstance(project, dict):
        raise TypeError("project must be a render configuration object")
    _text(project.get("title"), "project.title")
    for name in ("width", "height"):
        value = project.get(name)
        if type(value) is not int or value <= 0 or value % 2:
            raise ValueError(f"project.{name} must be a positive even integer")
    fps = project.get("fps")
    if type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0:
        raise ValueError("project.fps must be positive and finite")
    assets = plan.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("assets must be a non-empty array")
    by_id = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise TypeError("Each asset must be an object")
        identity = _text(asset.get("id"), "asset.id")
        if identity in by_id:
            raise ValueError(f"Duplicate asset id: {identity}")
        by_id[identity] = asset
        kind, source = asset.get("kind"), asset.get("source")
        if kind not in {"image", "video", "music", "sticker"}:
            raise ValueError(f"Unsupported asset kind: {kind}")
        if source not in {"local", "host_image", "external_video"}:
            raise ValueError(f"Unsupported asset source: {source}")
        if source == "host_image" and kind not in {"image", "sticker"}:
            raise ValueError("host_image requires image or sticker kind")
        if source == "external_video" and kind != "video":
            raise ValueError("external_video requires video kind")
        _text(asset.get("path"), f"{identity}.path")
        if source != "local":
            _text(asset.get("prompt"), f"{identity}.prompt")
        if not isinstance(asset.get("references", []), list):
            raise TypeError(f"{identity}.references must be an array of local paths")
        for reference in asset.get("references", []):
            _text(reference, f"{identity}.reference")
        if not isinstance(asset.get("tags", []), list) or any(
            not isinstance(tag, str) for tag in asset.get("tags", [])
        ):
            raise ValueError(f"{identity}.tags must be an array of strings")
    scenes = project.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("project.scenes must be a non-empty array")
    for scene in scenes:
        if not isinstance(scene, dict):
            raise TypeError("Each scene must be an object")
        _text(scene.get("label"), "scene.label")
        if not isinstance(scene.get("lines"), list) or not scene["lines"]:
            raise ValueError("Every scene must provide non-empty lines")
        for line in scene["lines"]:
            _text(line, "scene line")
        identity = _text(scene.get("material_id"), "scene.material_id")
        kind = scene.get("kind", "video")
        if (
            kind not in {"image", "video"}
            or identity not in by_id
            or by_id[identity]["kind"] != kind
        ):
            raise ValueError(f"Scene material missing or kind mismatch: {identity}")
        if scene.get("sticker") and (
            scene["sticker"] not in by_id
            or by_id[scene["sticker"]]["kind"] != "sticker"
        ):
            raise ValueError(f"Unknown sticker: {scene['sticker']}")
    if "publication" in plan and not isinstance(plan["publication"], dict):
        raise ValueError("publication must be an object, separate from narration")


def prepare_creation(plan_path: Path, output: Path) -> dict:
    """Inspect local artifacts and emit host tasks or render inputs in a new folder."""
    plan_path, output = plan_path.resolve(), output.resolve()
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    validate_plan(plan)
    # Reserve a fresh directory before writing; never replace a prior handoff.
    output.mkdir(parents=True, exist_ok=False)
    materials, tasks, failures = [], [], []
    for asset in plan["assets"]:
        path = _path(asset["path"], plan_path.parent)
        references = [_path(p, plan_path.parent) for p in asset.get("references", [])]
        if not path.exists():
            action = {
                "local": "provide_local_file",
                "host_image": "generate_image_with_host",
                "external_video": "external_video_required",
            }[asset["source"]]
            tasks.append(
                {
                    "asset_id": asset["id"],
                    "action": action,
                    "kind": asset["kind"],
                    "output_path": str(path),
                    "prompt": asset.get("prompt"),
                    "references": [str(p) for p in references],
                    "missing_references": [
                        str(p) for p in references if not p.is_file()
                    ],
                    "transparent_background": asset["kind"] == "sticker",
                }
            )
            continue
        try:
            measured = inspect_material(path, asset["kind"])
            if asset.get("sha256") and measured["sha256"] != asset["sha256"]:
                raise ValueError("Local asset SHA-256 differs from plan")
            materials.append(
                {
                    **measured,
                    "id": asset["id"],
                    "kind": asset["kind"],
                    "tags": asset.get("tags", []),
                    "credit": asset.get("credit", "Unspecified; see creation metadata"),
                    "license": asset.get("license", "unknown"),
                    "creation": {
                        "source": asset["source"],
                        "prompt": asset.get("prompt"),
                        "references": [str(p) for p in references],
                        "generation": asset.get("generation"),
                    },
                }
            )
        except (OSError, ValueError, RuntimeError) as exc:
            failures.append(
                {"asset_id": asset["id"], "path": str(path), "error": str(exc)}
            )
    status = "invalid" if failures else "pending" if tasks else "ready"
    report = {
        "schema": SCHEMA,
        "status": status,
        "plan_path": str(plan_path),
        "plan_sha256": hashlib.sha256(raw).hexdigest(),
        "tasks": tasks,
        "failures": failures,
        "assets_ready": len(materials),
        "execution": {"model_calls": 0, "network_requests": 0},
    }
    write_json(output / "creation-plan.json", plan)
    write_json(output / "creation-report.json", report)
    write_json(output / "asset-requests.json", tasks)
    write_json(output / "publication.json", plan.get("publication", {}))
    if status == "ready":
        write_json(output / "project.json", plan["project"])
        write_json(output / "materials.json", materials)
    return report
