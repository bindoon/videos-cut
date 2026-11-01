"""Platform-independent frame sampling and image geometry. No ASR or model calls."""
from __future__ import annotations

import hashlib
import io
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

from .media import probe


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return result


def video_info(source: Path) -> dict:
    source = source.expanduser().resolve(strict=True)
    info = probe(source)
    stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not stream:
        raise ValueError("Source has no video stream")
    seconds = float(stream.get("duration") or info["format"]["duration"])
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Video duration must be positive")
    return {"path": str(source), "sha256": sha256(source), "duration": seconds,
            "width": stream["width"], "height": stream["height"],
            "codec": stream["codec_name"]}


def grab_frame(source: Path, time: float, duration: float) -> Image.Image:
    time = number(time, "frame time", 0, duration)
    if time >= duration:
        raise ValueError("Frame time must be before video end")
    # Input seek lands near the GOP; output seek decodes to the requested position.
    preseek = max(0.0, time - 3.0)
    try:
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-ss", f"{preseek:.9f}", "-i", str(source),
            "-ss", f"{time - preseek:.9f}", "-frames:v", "1", "-f", "image2pipe",
            "-vcodec", "png", "pipe:1",
        ], capture_output=True, timeout=120, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Frame decode timed out at {time}s") from exc
    if result.returncode or not result.stdout:
        raise ValueError(f"Frame decode failed at {time}s: "
                         + result.stderr.decode(errors="replace")[-1200:])
    with Image.open(io.BytesIO(result.stdout)) as opened:
        return opened.convert("RGB")


def band_box(image: Image.Image, band: list) -> tuple[int, int, int, int]:
    if not isinstance(band, list) or len(band) != 2:
        raise ValueError("band must be [top, bottom] fractions")
    top, bottom = [number(v, "band boundary", 0, 1) for v in band]
    a, b = round(image.height * top), round(image.height * bottom)
    if a >= b:
        raise ValueError("band top must be below bottom with at least one pixel")
    return 0, a, image.width, b


def difference(a: Image.Image, b: Image.Image) -> float:
    a = a.convert("L").resize((160, 60))
    b = b.convert("L").resize((160, 60))
    changed = ImageChops.difference(a, b).point(lambda v: 255 if v > 12 else 0)
    return changed.histogram()[255] / (160 * 60)


def frame_metrics(image: Image.Image) -> dict:
    gray = image.convert("L").resize((160, 90))
    histogram = gray.histogram()
    return {"dark_fraction": sum(histogram[:12]) / (160 * 90),
            "edge_variance": round(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0], 3)}


def contact_sheet(images: list[Image.Image], labels: list[str] | None = None,
                  *, columns: int = 3, tile: tuple[int, int] = (320, 240)) -> Image.Image:
    if not images or not 1 <= columns <= 12:
        raise ValueError("Contact sheet requires images and 1–12 columns")
    label_height = 24 if labels else 0
    sheet = Image.new("RGB", (tile[0] * columns,
                              (tile[1] + label_height) * math.ceil(len(images) / columns)), "#12171d")
    draw = ImageDraw.Draw(sheet)
    for i, image in enumerate(images):
        x, y = i % columns * tile[0], i // columns * (tile[1] + label_height)
        thumb = ImageOps.contain(image.convert("RGB"), tile, Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x + (tile[0] - thumb.width) // 2,
                           y + (tile[1] - thumb.height) // 2))
        if labels:
            draw.text((x + 8, y + tile[1] + 4), labels[i], fill="white")
    return sheet


def sample_frames(source: Path, output: Path, *, times: list[float] | None = None,
                  around: float = 0, count: int = 12) -> dict:
    info = video_info(source)
    number(around, "around", 0, 10)
    if isinstance(count, bool) or not 1 <= count <= 48:
        raise ValueError("count must be 1–48")
    if times:
        for time in times:
            if number(time, "frame time", 0, info["duration"]) >= info["duration"]:
                raise ValueError("Frame time must be before video end")
        expanded = [t + delta for t in times for delta in (-around, 0, around)]
        picks = sorted({round(t, 9) for t in expanded if 0 <= t < info["duration"]})
    else:
        picks = [info["duration"] * (i + 0.5) / count for i in range(count)]
    if len(picks) > 144:
        raise ValueError("At most 144 candidate frames per call")
    output = output.expanduser().resolve()
    if output == Path(info["path"]) or output.exists():
        raise FileExistsError(f"Choose a new output directory: {output}")
    output.mkdir(parents=True)
    frames, records = [], []
    for i, time in enumerate(picks):
        frame = grab_frame(Path(info["path"]), time, info["duration"])
        path = output / f"frame-{i:03d}.png"
        frame.save(path)
        records.append({"time": time, "file": path.name, "sha256": sha256(path),
                        "width": frame.width, "height": frame.height, **frame_metrics(frame)})
        frames.append(frame)
    sheet = output / "contact-sheet.jpg"
    contact_sheet(frames, [f"{t:.3f}s" for t in picks]).save(sheet, quality=90)
    if sha256(Path(info["path"])) != info["sha256"]:
        raise ValueError("Source changed during frame extraction")
    report = {"schema": "frame-sample-v1", "source": info, "frames": records,
              "contact_sheet": sheet.name,
              "timing": "requested seconds; decoded frame at or after requested position",
              "visual_review": "pending"}
    atomic_json(output / "sample-report.json", report)
    return report


def preview_band(source: Path, output: Path, *, time: float, band: list) -> dict:
    info = video_info(source)
    frame = grab_frame(Path(info["path"]), time, info["duration"])
    box = band_box(frame, band)
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new output directory: {output}")
    output.mkdir(parents=True)
    frame.save(output / "frame.png")
    frame.crop(box).save(output / "band.png")
    draw = ImageDraw.Draw(frame)
    for y in (box[1], box[3] - 1):
        draw.line((0, y, frame.width, y), fill="#ff3737", width=3)
    frame.save(output / "preview.png")
    if sha256(Path(info["path"])) != info["sha256"]:
        raise ValueError("Source changed during band preview")
    report = {"schema": "frame-band-v1", "source": info, "time": time,
              "box": list(box), "visual_review": "pending"}
    atomic_json(output / "band-report.json", report)
    return report
