import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from videocut.assets import download_materials, select_material
from videocut.creation import prepare_creation


@pytest.fixture
def plan(tmp_path):
    data = json.loads(
        (Path(__file__).parents[1] / "examples/creation-plan.json").read_text()
    )
    data["assets"][0]["path"] = "generated/coffee.png"
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path, data


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False))


def image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 48), "brown").save(path)


def test_host_handoff_then_local_catalog_is_render_compatible(
    plan, tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Local preparation must not fetch remote content")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    monkeypatch.setattr("videocut.downloads.Importer.acquire", forbidden)
    path, data = plan
    before = path.read_bytes()
    pending = prepare_creation(path, tmp_path / "first")
    assert pending["status"] == "pending"
    task = pending["tasks"][0]
    assert task["action"] == "generate_image_with_host"
    assert task["prompt"] == data["assets"][0]["prompt"]
    assert not (tmp_path / "first/project.json").exists()
    image(Path(task["output_path"]))
    source = Path(task["output_path"]).read_bytes()
    ready = prepare_creation(path, tmp_path / "second")
    assert ready["status"] == "ready"
    assert ready["execution"] == {"model_calls": 0, "network_requests": 0}
    project = json.loads((tmp_path / "second/project.json").read_text())
    assert project == data["project"]
    assert (
        json.loads((tmp_path / "second/publication.json").read_text())
        == data["publication"]
    )
    materials = download_materials(
        tmp_path / "second/materials.json", tmp_path / "cache"
    )
    selected = select_material(project["scenes"][0], materials, {})
    assert selected["path"] == task["output_path"]
    assert selected["sha256"] == hashlib.sha256(source).hexdigest()
    assert selected["creation"]["prompt"] == task["prompt"]
    assert path.read_bytes() == before
    assert Path(task["output_path"]).read_bytes() == source
    with pytest.raises(FileExistsError):
        prepare_creation(path, tmp_path / "second")


def test_external_video_and_missing_reference_remain_explicit(plan, tmp_path):
    path, data = plan
    data["assets"][0].update(
        kind="video",
        source="external_video",
        path="video.mp4",
        references=["reference.png"],
    )
    data["project"]["scenes"][0]["kind"] = "video"
    save(path, data)
    report = prepare_creation(path, tmp_path / "out")
    assert report["status"] == "pending"
    assert report["tasks"][0]["action"] == "external_video_required"
    assert report["tasks"][0]["missing_references"] == [str(tmp_path / "reference.png")]
    assert not (tmp_path / "video.mp4").exists()


@pytest.mark.parametrize(
    "bad_bytes,checksum", [(b"not an image", None), (None, "0" * 64)]
)
def test_corrupt_or_changed_file_cannot_be_ready(plan, tmp_path, bad_bytes, checksum):
    path, data = plan
    target = tmp_path / data["assets"][0]["path"]
    image(target)
    if bad_bytes:
        target.write_bytes(bad_bytes)
    if checksum:
        data["assets"][0]["sha256"] = checksum
        save(path, data)
    report = prepare_creation(path, tmp_path / "out")
    assert report["status"] == "invalid"
    assert report["failures"][0]["asset_id"] == "morning-coffee"
    assert not (tmp_path / "out/materials.json").exists()


@pytest.mark.parametrize(
    "change",
    ["duplicate", "unbound", "wrong_kind", "empty_line", "odd_width", "no_prompt"],
)
def test_invalid_plan_fails_before_creating_output(plan, tmp_path, change):
    path, data = plan
    if change == "duplicate":
        data["assets"].append(copy.deepcopy(data["assets"][0]))
    elif change == "unbound":
        data["project"]["scenes"][0]["material_id"] = "unknown"
    elif change == "wrong_kind":
        data["project"]["scenes"][0]["kind"] = "video"
    elif change == "empty_line":
        data["project"]["scenes"][0]["lines"] = [" "]
    elif change == "odd_width":
        data["project"]["width"] = 721
    else:
        data["assets"][0]["prompt"] = ""
    save(path, data)
    with pytest.raises(ValueError):
        prepare_creation(path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_cli_pending_without_ffmpeg_and_ready_after_host_file(plan, tmp_path):
    path, data = plan
    env = {**os.environ, "PATH": ""}
    command = [
        sys.executable,
        "-m",
        "videocut",
        "prepare",
        "--plan",
        str(path),
        "--output",
    ]
    result = subprocess.run(
        command + [str(tmp_path / "pending")],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["status"] == "pending"
    image(tmp_path / data["assets"][0]["path"])
    result = subprocess.run(
        command + [str(tmp_path / "ready")],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "ready"
