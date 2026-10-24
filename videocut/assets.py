from __future__ import annotations

import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def download_materials(catalog: Path, cache: Path) -> list[dict]:
    cache.mkdir(parents=True, exist_ok=True)
    materials = json.loads(catalog.read_text())

    def fetch(item: dict) -> dict:
        item = dict(item)
        filename = item.get("filename", "")
        if not filename or Path(filename).name != filename:
            raise ValueError(f"Invalid material filename: {filename}")
        target = cache / filename
        if "path" in item:
            target = Path(item["path"]).expanduser().resolve()
            if not target.is_file():
                raise FileNotFoundError(target)
        elif not target.exists():
            print(f"下载素材: {item['id']}", flush=True)
            temporary = target.with_suffix(target.suffix + ".part")
            try:
                request = urllib.request.Request(
                    item["url"],
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": item.get("page", ""),
                    },
                )
                with urllib.request.urlopen(request, timeout=90) as response:
                    size = 0
                    with temporary.open("wb") as stream:
                        while chunk := response.read(1024 * 256):
                            size += len(chunk)
                            if size > 250 * 1024 * 1024:
                                raise ValueError("Material exceeds 250 MB")
                            stream.write(chunk)
                if size == 0:
                    raise ValueError("Empty material response")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        item["path"] = str(target.resolve())
        with target.open("rb") as stream:
            item["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        item["bytes"] = target.stat().st_size
        return item

    with ThreadPoolExecutor(max_workers=4) as executor:
        result = list(executor.map(fetch, materials))
    (cache / "sources.lock.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    return result


def select_material(scene: dict, materials: list[dict], used: dict[str, int]) -> dict:
    candidates = [
        item for item in materials if item["kind"] == scene.get("kind", "video")
    ]
    if scene.get("material_id"):
        candidates = [item for item in candidates if item["id"] == scene["material_id"]]
    if not candidates:
        raise ValueError(f"No material for scene: {scene['label']}")
    query = scene.get("query", [])

    def rank(item: dict) -> tuple:
        score = sum(
            1
            for word in query
            if any(word in tag or tag in word for tag in item.get("tags", []))
        )
        return score - used.get(item["id"], 0) * 1.1, -used.get(item["id"], 0)

    selected = max(candidates, key=rank)
    used[selected["id"]] = used.get(selected["id"], 0) + 1
    return selected
