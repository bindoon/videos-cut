"""Build README media from existing delivered films, never from preview renders.

Run from the repository: uv run python scripts/build_readme_gallery.py --output outputs/gallery-new
Review the images before copying its gallery/ files to docs/media/.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from PIL import Image

from videocut.image_cards import render_cards, verify_cards
from videocut.image_ops import atomic_json, contact_sheet, sample_frames, sha256

FILMS = [
    {"id": "hangzhou", "session": "制定代码复刻视频方案",
     "source": "outputs/hangzhou-two-minute-qianchen-20261030/delivery-v2/杭州-城市年轮-钱陈音色-两分钟.mp4",
     "times": [3.578, 21.2, 45.492, 60.635, 85.892, 110.082],
     "credits": "films/hangzhou/CREDITS.md; films/hangzhou/MONTAGE-CREDITS.md"},
    {"id": "butterfly", "session": "制作机械蝴蝶",
     "source": "outputs/mechanical-butterfly-v2-20261031/final.mp4",
     "times": [3.8, 8.8, 14.5, 17.5, 24, 28],
     "credits": "films/mechanical-butterfly/CINEMATIC.md"},
    {"id": "taiji", "session": "制作太极缠丝劲动画",
     "source": "outputs/taiji-flow-v3-20261102/delivery/final.mp4",
     "times": [3, 9.5, 13.9, 16.6, 27.4, 33.4],
     "credits": "films/taiji-silk/CREDITS-V2.md; CC BY-SA 4.0"},
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    gallery = output / "gallery"
    gallery.mkdir()
    records = []
    for film in FILMS:
        job = output / film["id"]
        report = sample_frames(root / film["source"], job, times=film["times"])
        frames = []
        for item in report["frames"]:
            with Image.open(job / item["file"]) as image:
                frames.append(image.convert("RGB"))
        target = gallery / f"{film['id']}-gallery.jpg"
        contact_sheet(frames, [f"{t:.3f}s" for t in film["times"]],
                      tile=(480, 270)).save(target, quality=91)
        records.append({**film, "video": {k: v for k, v in report["source"].items() if k != "path"},
                        "image": target.name, "image_sha256": sha256(target),
                        "transformation": "Decoded delivered frames, uniform thumbnail scaling, time labels"})
    native = {"schema": "image-cards-v1", "source": str(root / FILMS[0]["source"]),
              "mode": "native", "style": {"width": 1080, "layout": "natural", "band": [0.84, 0.98]},
              "cards": [{"id": "hangzhou-history", "title": "苏堤与临安：原片连续四句",
                         "lines": [{"time": t} for t in [40.782, 45.492, 50.906, 55.837]]}]}
    scripted = {"schema": "image-cards-v1", "source": str(root / FILMS[1]["source"]),
                "mode": "script", "style": {"width": 720, "layout": "fixed", "aspect": [3, 4],
                "band": [0.55, 0.82], "hero_fraction": 0.52, "font_size": 26, "fit": "cover"},
                "cards": [{"id": "butterfly-explained", "title": "机械概念动画的后期说明",
                           "lines": []}]}
    texts = ["机械蝴蝶：从外形走进内部", "俯视四翼，观察结构与层次", "移开翼组件，展示电机剖视",
             "推近齿轮，观察传动示意", "分层展开，再看清各个部件"]
    for t, text in zip(FILMS[1]["times"][:5], texts, strict=True):
        scripted["cards"][0]["lines"].append({"time": t, "text": text, "reviewed": True,
            "text_source": {"kind": "user", "reference": "scripts/build_readme_gallery.py; "
                            "author commentary based on films/mechanical-butterfly/CINEMATIC.md"}})
    for name, manifest in (("native", native), ("script", scripted)):
        manifest_path = output / f"{name}-manifest.json"
        atomic_json(manifest_path, manifest)
        report = render_cards(manifest_path, output / f"cards-{name}")
        if report["status"] != "ready":
            raise ValueError(json.dumps(report["failures"], ensure_ascii=False))
        verification = verify_cards(output / f"cards-{name}/image-report.json")
        atomic_json(output / f"{name}-verification.json", verification)
        target = gallery / f"cards-{name}.jpg"
        target.write_bytes((output / f"cards-{name}" / report["results"][0]["file"]).read_bytes())
        # Portable source paths in the published manifest, relative to docs/media/.
        manifest["source"] = "../../" + (FILMS[0] if name == "native" else FILMS[1])["source"]
        manifest["source_sha256"] = report["request"]["source"]["sha256"]
        atomic_json(gallery / f"cards-{name}.json", manifest)
        records.append({"image": target.name, "image_sha256": sha256(target), "mode": name,
                        "manifest": f"cards-{name}.json", "verification": verification,
                        "text_origin": report["results"][0]["text_origin"]})
    atomic_json(gallery / "gallery-source.json", {"schema": "readme-gallery-v1", "date": date.today().isoformat(),
                "source_selection": "Prior project sessions, cross-checked against local delivered files",
                "visual_review": "pending", "items": records})
    print(json.dumps({"gallery": str(gallery), "items": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
