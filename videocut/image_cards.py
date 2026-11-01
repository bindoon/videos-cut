"""Generic video-frame cards: pixel-preserving strips or reviewed scripted text."""
from __future__ import annotations

import fcntl
import json
import re
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .image_ops import (
    atomic_json,
    band_box,
    contact_sheet,
    difference,
    fingerprint,
    frame_metrics,
    grab_frame,
    number,
    sha256,
    video_info,
)

SCHEMA = "image-cards-v1"
RENDERER = "frame-card-render-v1"
STYLE_KEYS = {"layout", "width", "aspect", "band", "hero_fraction", "font", "font_size",
              "strip_gap", "background", "text_color", "emphasis_color", "fit"}


def _path(value: str, root: Path) -> Path:
    p = Path(value).expanduser()
    return (p if p.is_absolute() else root / p).resolve(strict=True)


def _integer(value: object, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _font(style: dict, root: Path) -> dict:
    if style.get("font"):
        path = _path(style["font"], root)
    else:
        from .render import find_font
        path = Path(find_font()).resolve(strict=True)
    ImageFont.truetype(str(path), 24)
    return {"path": str(path), "sha256": sha256(path)}


def plan_cards(manifest: Path) -> dict:
    manifest = manifest.expanduser().resolve(strict=True)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError(f"Expected schema {SCHEMA}")
    unknown = set(data) - {"schema", "source", "source_sha256", "mode", "style", "cards"}
    if unknown:
        raise ValueError(f"Unknown manifest fields: {sorted(unknown)}")
    source = video_info(_path(data["source"], manifest.parent))
    if data.get("source_sha256") and data["source_sha256"] != source["sha256"]:
        raise ValueError("Source checksum mismatch")
    mode = data.get("mode")
    if mode not in {"native", "script"}:
        raise ValueError("mode must explicitly be native or script")
    supplied = data.get("style", {})
    if not isinstance(supplied, dict) or set(supplied) - STYLE_KEYS:
        raise ValueError("Unknown image style fields")
    style = {"layout": "natural" if mode == "native" else "fixed", "width": 1080,
             "aspect": [3, 4], "band": [0.76, 0.96], "hero_fraction": 0.64,
             "font_size": 40, "strip_gap": 0, "background": "#12171d",
             "text_color": "#ffffff", "emphasis_color": "#ffda86", "fit": "contain",
             **supplied}
    if style["layout"] not in {"natural", "fixed"} or style["fit"] not in {"contain", "cover"}:
        raise ValueError("layout must be natural/fixed; fit must be contain/cover")
    _integer(style["width"], "width", 240, 4096)
    _integer(style["font_size"], "font_size", 12, 200)
    _integer(style["strip_gap"], "strip_gap", 0, 24)
    number(style["hero_fraction"], "hero_fraction", 0.35, 0.85)
    aspect = style["aspect"]
    if not isinstance(aspect, list) or len(aspect) != 2:
        raise ValueError("aspect must be [width, height]")
    for value in aspect:
        number(value, "aspect", 1, 20)
    target_height = round(style["width"] * aspect[1] / aspect[0])
    if target_height > 8192 or target_height < 240:
        raise ValueError("Fixed canvas height must be 240–8192")
    band_box(Image.new("RGB", (source["width"], source["height"])), style["band"])
    # Native mode always scales the complete pixel stack once, then pads if fixed.
    if mode == "native" and (style["fit"] != "contain" or "font" in supplied
                             or set(supplied) & {"font_size", "text_color", "emphasis_color",
                                                "hero_fraction"}):
        raise ValueError("Native mode preserves pixels; text and hero sizing options are forbidden")
    font = _font(style, manifest.parent) if mode == "script" else None
    if font:
        style["font"] = font["path"]
    # Validate colors before starting an output job.
    for color in (style["background"], style["text_color"], style["emphasis_color"]):
        Image.new("RGB", (1, 1), color)
    cards = data.get("cards")
    if not isinstance(cards, list) or not 1 <= len(cards) <= 100:
        raise ValueError("cards must contain 1–100 items")
    seen, normalized = set(), []
    for card in cards:
        if not isinstance(card, dict) or set(card) - {"id", "title", "lines", "duplicate_reason"}:
            raise ValueError("Unknown card fields")
        identity = card.get("id", "")
        if not isinstance(identity, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", identity):
            raise ValueError("Card id must be a safe, nonempty ASCII name")
        if identity in seen:
            raise ValueError("Duplicate card id")
        seen.add(identity)
        lines = card.get("lines")
        if not isinstance(lines, list) or not 2 <= len(lines) <= 7:
            raise ValueError("Each card requires 2–7 chronological lines")
        last = -1
        for line in lines:
            if not isinstance(line, dict):
                raise TypeError("Each line must be an object")
            allowed = {"time"} if mode == "native" else {"time", "text", "speaker", "emphasis",
                                                          "reviewed", "text_source"}
            if set(line) - allowed:
                raise ValueError(f"Invalid {mode} line fields; native lines only contain time")
            t = number(line.get("time"), "line time", 0, source["duration"])
            if t >= source["duration"] or t <= last:
                raise ValueError("Line times must strictly increase and precede video end")
            last = t
            if mode == "script":
                text = line.get("text")
                provenance = line.get("text_source")
                if not isinstance(text, str) or not text.strip() or len(text) > 500:
                    raise ValueError("Script text must contain 1–500 characters")
                if line.get("reviewed") is not True:
                    raise ValueError("Script text must be reviewed before rendering")
                if (not isinstance(provenance, dict)
                    or provenance.get("kind") not in {"user", "asr", "platform", "translation", "edited"}
                    or not isinstance(provenance.get("reference"), str)
                    or not provenance["reference"].strip()):
                    raise ValueError("Script text_source requires kind and reference")
                if "speaker" in line and (not isinstance(line["speaker"], str) or len(line["speaker"]) > 40):
                    raise ValueError("speaker must be a short string")
                if "emphasis" in line and not isinstance(line["emphasis"], bool):
                    raise ValueError("emphasis must be boolean")
        reason = card.get("duplicate_reason")
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError("duplicate_reason must explain an intentional repeated strip")
        job = {**card, "lines": lines}
        job["key"] = fingerprint({"renderer": RENDERER, "source": source["sha256"],
                                   "mode": mode, "style": style, "font": font, "card": card})
        normalized.append(job)
    if font:
        face = ImageFont.truetype(font["path"], 24)
        missing = face.getmask(chr(0x10FFFF))
        text = "".join(line["text"] + line.get("speaker", "") for card in normalized for line in card["lines"])
        for char in set(text):
            glyph = face.getmask(char)
            if not char.isspace() and glyph.size == missing.size and bytes(glyph) == bytes(missing):
                raise ValueError(f"Font has no glyph for {char!r}; choose a suitable font")
    result = {"schema": SCHEMA, "renderer": RENDERER, "mode": mode, "source": source,
              "style": style, "font": font, "cards": normalized}
    result["key"] = fingerprint(result)
    return result


def _wrap(text: str, draw: ImageDraw.ImageDraw, font, width: int) -> list[str]:
    rows, row = [], ""
    for char in text:
        if char == "\n" or draw.textlength(row + char, font=font) > width:
            if row:
                rows.append(row)
            row = "" if char == "\n" else char
        else:
            row += char
        if row and draw.textlength(row, font=font) > width:
            raise ValueError("A text glyph exceeds the available width")
    if row:
        rows.append(row)
    return rows


def _script_text(image: Image.Image, line: dict, style: dict, *, hero: bool = False) -> list:
    draw = ImageDraw.Draw(image)
    size = style["font_size"]
    font = ImageFont.truetype(style["font"], size)
    text = (line["speaker"] + ": " if line.get("speaker") else "") + line["text"]
    margin = max(12, round(image.width * 0.035))
    rows = _wrap(text, draw, font, image.width - 2 * margin)
    spacing, pad = round(size * 1.3), max(10, size // 3)
    required = spacing * len(rows) + 2 * pad
    if required > image.height:
        raise ValueError("Text exceeds strip height; split lines, change layout or reduce font_size")
    top = image.height - required if hero else (image.height - required) // 2
    # Dark translucent backing is deliberate and only belongs to script mode.
    overlay = Image.new("RGBA", image.size)
    ImageDraw.Draw(overlay).rectangle((0, top, image.width, top + required), fill=(7, 12, 20, 210))
    image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))
    draw = ImageDraw.Draw(image)
    boxes = []
    for i, row in enumerate(rows):
        x = (image.width - draw.textlength(row, font=font)) / 2
        y = top + pad + i * spacing
        draw.text((x, y), row, font=font, anchor="lt", stroke_width=1,
                  fill=style["emphasis_color"] if line.get("emphasis") else style["text_color"],
                  stroke_fill="#000000")
        box = draw.textbbox((x, y), row, font=font, anchor="lt", stroke_width=1)
        if box[0] < 0 or box[1] < 0 or box[2] > image.width or box[3] > image.height:
            raise ValueError("Rendered text exceeds image boundary")
        boxes.append(list(box))
    return boxes


def render_card(request: dict, card: dict) -> tuple[Image.Image, dict]:
    style, source = request["style"], request["source"]
    frames = [grab_frame(Path(source["path"]), line["time"], source["duration"])
              for line in card["lines"]]
    if len({image.size for image in frames}) != 1:
        raise ValueError("Source frame dimensions changed")
    warnings, metrics = [], [frame_metrics(frame) for frame in frames]
    if any(m["dark_fraction"] > 0.98 for m in metrics):
        warnings.append("Candidate contains a nearly black frame; review or select another time")
    band = band_box(frames[0], style["band"])
    strips = [frame.crop(band) for frame in frames]
    duplicate_pairs = [i for i in range(1, len(strips)) if difference(strips[i - 1], strips[i]) < 0.005]
    if duplicate_pairs:
        if request["mode"] == "native" and not card.get("duplicate_reason"):
            raise ValueError(f"Repeated subtitle strips at lines {duplicate_pairs}; inspect candidates")
        warnings.append("Similar strip backgrounds; visual review required")
    width, boxes = style["width"], []
    if request["mode"] == "native":
        parts = [frames[0].crop((0, 0, frames[0].width, band[3])), *strips[1:]]
        # Gap is defined in output pixels; scale it back before the one shared resize.
        gap = round(style["strip_gap"] * frames[0].width / width)
        stack = Image.new("RGB", (frames[0].width,
                                  sum(p.height for p in parts) + gap * (len(parts) - 1)),
                          style["background"])
        y = 0
        for part in parts:
            stack.paste(part, (0, y))
            y += part.height + gap
        natural_size = (width, round(stack.height * width / stack.width))
        if style["layout"] == "fixed":
            size = (width, round(width * style["aspect"][1] / style["aspect"][0]))
            image = ImageOps.pad(stack, size, Image.Resampling.LANCZOS, color=style["background"])
        else:
            image = stack.resize(natural_size, Image.Resampling.LANCZOS)
    else:
        if style["layout"] == "fixed":
            height = round(width * style["aspect"][1] / style["aspect"][0])
            hero_height = round(height * style["hero_fraction"])
            remaining = height - hero_height - style["strip_gap"] * (len(frames) - 1)
            heights = [hero_height] + [remaining // (len(frames) - 1)] * (len(frames) - 1)
            heights[-1] += height - sum(heights) - style["strip_gap"] * (len(frames) - 1)
        else:
            heights = [round(frames[0].height * width / frames[0].width)]
            heights += [round(strips[0].height * width / strips[0].width)] * (len(frames) - 1)
            height = sum(heights) + style["strip_gap"] * (len(frames) - 1)
        image = Image.new("RGB", (width, height), style["background"])
        y = 0
        for i, (frame, strip_height, line) in enumerate(zip(frames, heights, card["lines"], strict=True)):
            base = frame if i == 0 else frame.crop(band)
            if style["fit"] == "cover":
                part = ImageOps.fit(base, (width, strip_height), Image.Resampling.LANCZOS)
            else:
                part = ImageOps.pad(base, (width, strip_height), Image.Resampling.LANCZOS,
                                    color=style["background"])
            local_boxes = _script_text(part, line, style, hero=i == 0)
            boxes.extend([[b[0], b[1] + y, b[2], b[3] + y] for b in local_boxes])
            image.paste(part, (0, y))
            y += strip_height + style["strip_gap"]
    if width > frames[0].width:
        warnings.append("Output upscales source pixels; it does not increase source detail")
    return image, {"width": image.width, "height": image.height, "text_boxes": boxes,
                   "frame_metrics": metrics, "duplicate_pairs": duplicate_pairs,
                   "warnings": warnings, "visual_review": "pending",
                   "text_origin": "source_pixels" if request["mode"] == "native" else "post_added",
                   "semantic_verified": False}


@contextmanager
def _lock(output: Path):
    with (output / ".images.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another images render owns this output directory") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _valid_record(record: dict, output: Path) -> bool:
    try:
        path = output / record["file"]
        if path.resolve().parent != output or sha256(path) != record["sha256"]:
            return False
        with Image.open(path) as image:
            image.load()
            return image.size == (record["width"], record["height"])
    except (OSError, ValueError, KeyError):
        return False


def render_cards(manifest: Path, output: Path, *, resume: bool = False,
                 keep_going: bool = False) -> dict:
    request = plan_cards(manifest)
    output = output.expanduser().resolve()
    if output.exists() and not resume:
        raise FileExistsError(f"Choose a new output directory or --resume: {output}")
    output.mkdir(parents=True, exist_ok=True)
    with _lock(output):
        report_path = output / "image-report.json"
        if not resume and report_path.exists():
            raise FileExistsError(f"Output already contains an image task: {output}")
        previous = {}
        if resume:
            if not report_path.is_file():
                raise ValueError("--resume requires an existing image-report.json")
            previous = json.loads(report_path.read_text(encoding="utf-8"))
            if previous.get("schema") != RENDERER:
                raise ValueError("Unrecognized previous image report")
        old = {r["key"]: r for r in previous.get("results", []) if r.get("status") == "ready"}
        report = {"schema": RENDERER, "request": request, "status": "running", "results": [],
                  "failures": [], "contact_sheet": None, "reused": 0,
                  "visual_review": "pending", "semantic_verified": False}
        atomic_json(report_path, report)
        for card in request["cards"]:
            path = output / f"{card['id']}-{card['key'][:16]}.jpg"
            record = {"id": card["id"], "key": card["key"], "status": "failed"}
            try:
                cached = old.get(card["key"])
                if cached and _valid_record(cached, output):
                    record = cached
                    report["reused"] += 1
                else:
                    if cached and (output / cached["file"]).resolve().parent == output:
                        path = output / cached["file"]
                    elif path.exists():
                        # A crash can occur after image commit but before report commit.
                        # Preserve those unregistered bytes; produce a new owned revision.
                        revision = 1
                        while path.exists():
                            path = output / f"{card['id']}-{card['key'][:16]}-recovered-{revision}.jpg"
                            revision += 1
                    image, checks = render_card(request, card)
                    temporary = path.with_suffix(".jpg.tmp")
                    image.save(temporary, format="JPEG", quality=95, subsampling=0)
                    temporary.replace(path)
                    record = {**record, "status": "ready", "file": path.name,
                              "sha256": sha256(path), **checks}
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                record["error"] = str(exc)
                report["failures"].append({"id": card["id"], "error": str(exc)})
            report["results"].append(record)
            atomic_json(report_path, report)
            if record["status"] == "failed" and not keep_going:
                break
        source_ok = sha256(Path(request["source"]["path"])) == request["source"]["sha256"]
        font_ok = not request["font"] or sha256(Path(request["font"]["path"])) == request["font"]["sha256"]
        if not source_ok or not font_ok:
            report["failures"].append({"id": "inputs", "error": "Source or font changed during render"})
        complete = len(report["results"]) == len(request["cards"]) and not report["failures"]
        if complete:
            images = []
            for record in report["results"]:
                with Image.open(output / record["file"]) as opened:
                    images.append(opened.convert("RGB"))
            sheet = output / f"contact-sheet-{request['key'][:16]}.jpg"
            contact_sheet(images, [r["id"] for r in report["results"]],
                          columns=min(3, len(images)), tile=(300, 400)).save(sheet, quality=90)
            report["contact_sheet"] = {"file": sheet.name, "sha256": sha256(sheet)}
        report["status"] = "ready" if complete else "failed"
        atomic_json(report_path, report)
        return report


def verify_cards(report_path: Path) -> dict:
    report_path = report_path.expanduser().resolve(strict=True)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema") != RENDERER or report.get("status") != "ready" or report.get("failures"):
        raise ValueError("Image report is incomplete or failed")
    request, records = report["request"], report["results"]
    if request["key"] != fingerprint({k: v for k, v in request.items() if k != "key"}):
        raise ValueError("Image request checksum mismatch")
    if len(records) != len(request["cards"]):
        raise ValueError("Image report is missing cards")
    if sha256(Path(request["source"]["path"])) != request["source"]["sha256"]:
        raise ValueError("Source checksum mismatch")
    font = request["font"]
    if font and sha256(Path(font["path"])) != font["sha256"]:
        raise ValueError("Font checksum mismatch")
    for card, record in zip(request["cards"], records, strict=True):
        if (record.get("status") != "ready" or card["id"] != record.get("id")
            or card["key"] != record.get("key") or not _valid_record(record, report_path.parent)):
            raise ValueError(f"Image checksum/geometry mismatch: {card['id']}")
        style = request["style"]
        if record["width"] != style["width"] or (style["layout"] == "fixed" and
            record["height"] != round(style["width"] * style["aspect"][1] / style["aspect"][0])):
            raise ValueError("Image dimensions differ from requested layout")
        for box in record["text_boxes"]:
            if not (0 <= box[0] < box[2] <= record["width"] and 0 <= box[1] < box[3] <= record["height"]):
                raise ValueError("Text outside image bounds")
    sheet = report.get("contact_sheet")
    if (not sheet or (report_path.parent / sheet["file"]).resolve().parent != report_path.parent
        or sha256(report_path.parent / sheet["file"]) != sheet["sha256"]):
        raise ValueError("Contact sheet checksum mismatch")
    return {"schema": "image-card-verification-v1", "mechanical_passed": True,
            "cards": len(records), "mode": request["mode"],
            "visual_review": "pending", "semantic_verified": False,
            "subtitle_sync": {"passed": None, "reason": "Still images; not audio alignment acceptance"}}
