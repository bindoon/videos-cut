from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from .downloads import (
    DownloadFailure,
    DownloadOptions,
    Importer,
    _error,
    atomic_json,
    inspect_material,
    make_report,
    save_report,
)


def import_catalog_items(
    items: list[dict],
    cache: Path,
    options: DownloadOptions | None = None,
    *,
    output: Path | None = None,
) -> dict:
    options = options or DownloadOptions()
    importer = Importer(cache, options)
    results = []
    for index, item in enumerate(items):
        try:
            filename = item.get("filename")
            if filename and (
                Path(filename).name != filename or filename in {".", ".."}
            ):
                raise ValueError(f"Invalid material filename: {filename}")
            if "path" in item:
                material = {
                    **item,
                    **inspect_material(
                        Path(item["path"]).expanduser().resolve(), item["kind"]
                    ),
                }
                if item.get("sha256") and material["sha256"] != item["sha256"]:
                    raise DownloadFailure(
                        "CHECKSUM_MISMATCH",
                        "Local material no longer matches its recorded SHA-256",
                    )
                # Existing local inputs are not constrained by remote transfer limits.
                rows = [
                    {
                        "url": item.get("url", item["path"]),
                        "status": "local",
                        "material": material,
                    }
                ]
            else:
                host = urlsplit(item["url"]).hostname or ""
                web_hosts = (
                    "youtube.com",
                    "youtu.be",
                    "bilibili.com",
                    "b23.tv",
                    "tiktok.com",
                    "tiktokv.com",
                    "weixin.qq.com",
                )
                source = item.get("source") or (
                    "web"
                    if any(host == h or host.endswith("." + h) for h in web_hosts)
                    else "direct"
                )
                importer.options = (
                    replace(options, mode="audio")
                    if item.get("kind") == "music" and source in {"web", "wechat"}
                    else options
                )
                if item.get("wechat_feed_id"):
                    importer.options = replace(
                        importer.options, wechat_feed_id=str(item["wechat_feed_id"])
                    )
                rows = importer.acquire(
                    item["url"],
                    source=source,
                    kind=item["kind"],
                    preferred=cache.resolve() / filename if filename else None,
                    referer=item.get("page", ""),
                )
                for row in rows:
                    if material := row.get("material"):
                        # User labels describe intended use; measured file facts stay authoritative.
                        labels = {
                            k: v
                            for k, v in item.items()
                            if k in {"id", "tags", "credit", "license", "page", "title"}
                        }
                        if len(rows) > 1 and "id" in labels:
                            labels["id"] += "-" + str(
                                material.get("source_id", material["id"])
                            )
                        material.update(labels)
            for row in rows:
                row["item"] = item
            results.extend(rows)
        except KeyboardInterrupt:
            for pending_index, pending in enumerate(items[index:]):
                results.append(
                    {
                        "url": pending.get("url", pending.get("path", "")),
                        "item": pending,
                        "status": "failed",
                        "error": {
                            "code": "NOT_ATTEMPTED" if pending_index else "INTERRUPTED",
                            "message": "Interrupted; retry this report to finish pending sources",
                        },
                    }
                )
            if output:
                save_report(make_report(results, cache, options), output)
            raise
        except Exception as exc:  # noqa: BLE001 -- collect independent material failures
            results.append(
                {
                    "url": item.get("url", item.get("path", "")),
                    "item": item,
                    "status": "failed",
                    "error": _error(exc),
                }
            )
        if output:
            save_report(make_report(results, cache, options), output)
    report = make_report(results, cache, options)
    atomic_json(cache / "download-report.json", report)
    atomic_json(cache / "sources.lock.json", report["materials"])
    return report


def download_catalog(
    catalog: Path,
    cache: Path,
    options: DownloadOptions | None = None,
    *,
    output: Path | None = None,
) -> dict:
    items = json.loads(catalog.read_text())
    if not isinstance(items, list):
        raise TypeError("Material catalog must be a JSON array")
    return import_catalog_items(items, cache, options, output=output)


def download_materials(catalog: Path, cache: Path) -> list[dict]:
    report = download_catalog(catalog, cache)
    if report["failed"]:
        failures = [
            r["error"]["message"] for r in report["results"] if r["status"] == "failed"
        ]
        raise RuntimeError(
            f"{report['failed']} material(s) failed; see {cache / 'download-report.json'}:\n"
            + "\n".join(failures)
        )
    return report["materials"]


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
