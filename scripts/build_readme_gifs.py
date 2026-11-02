"""Build small, silent README previews from the delivered films.

Run from the repository with --output pointing to a new directory. Inspect the
generated contact sheets before copying GIFs and gif-source.json to docs/media/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from build_readme_gallery import FILMS
from videocut.ffmpeg_tools import invoke_json
from videocut.image_ops import atomic_json, sha256

EXCERPTS = {
    "hangzhou": [(3, 5), (20, 22), (84, 86)],
    "butterfly": [(3, 5), (14, 16), (24, 26)],
    "taiji": [(2, 4), (11, 13), (25, 27)],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for film in FILMS:
        name = film["id"]
        source = root / film["source"]
        probe = invoke_json(["probe", str(source), "--json"], report=output / f"{name}-source.json")
        target = output / f"{name}-demo.gif"
        project = {
            "output": str(target),
            "frame": {"width": 480, "fps": 12},
            "clips": [{"src": str(source), "in": start, "out": end}
                      for start, end in EXCERPTS[name]],
            "transition": {"type": "none"},
            "export": {"preset": "gif"},
        }
        project_path = output / f"{name}-project.json"
        atomic_json(project_path, project)
        invoke_json(["render", str(project_path), "--dry-run", "--json"],
                    report=output / f"{name}-plan.json")
        result = invoke_json(["render", str(project_path), "--json"],
                             report=output / f"{name}-render.json")
        sheet = output / f"{name}-look.png"
        invoke_json(["look", str(target), "--tiles", "3x2", "-o", str(sheet), "--json"],
                    report=output / f"{name}-look.json")
        with Image.open(target) as gif:
            width, height = gif.size
            frames = gif.n_frames
            milliseconds = 0
            for index in range(frames):
                gif.seek(index)
                gif.load()
                milliseconds += gif.info["duration"]
            if (width, height) != (480, 270) or frames != 72 or abs(milliseconds - 6000) > 20:
                raise ValueError(f"Unexpected preview dimensions/timing: {target}")
            if gif.info.get("loop") != 0:
                raise ValueError(f"Preview must loop: {target}")
        records.append({
            "id": name, "source": film["source"], "source_sha256": sha256(source),
            "source_probe": probe.get("probe", probe), "credits": film["credits"],
            "excerpt_seconds": EXCERPTS[name], "image": target.name,
            "image_sha256": sha256(target), "bytes": target.stat().st_size,
            "width": width, "height": height, "frames": frames,
            "duration_ms": milliseconds, "audio": False,
            "transformation": "Three 2-second excerpts, hard cuts, uniform downscale, 12 fps palette GIF",
            "verified": result.get("verified"), "visual_review": "pending",
        })
    atomic_json(output / "gif-source.json", {"schema": "readme-gifs-v1", "items": records})
    print(json.dumps({"output": str(output), "gifs": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
