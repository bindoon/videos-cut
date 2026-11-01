from __future__ import annotations

import math
import os
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .assets import select_material
from .media import duration, probe, run, write_json


def find_font() -> str:
    candidates = [
        os.environ.get("VIDEOCUT_FONT", ""),
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Set VIDEOCUT_FONT to a Chinese TTF/OTF/TTC font")


def make_text(
    text: str, width: int, size: int, *, color="white", pill=False
) -> Image.Image:
    font = ImageFont.truetype(find_font(), size)
    measuring = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines, line = [], ""
    for char in text:
        if char == "\n" or measuring.textlength(line + char, font=font) > width - 48:
            lines.append(line)
            line = "" if char == "\n" else char
        else:
            line += char
    if line:
        lines.append(line)
    height = len(lines) * (size + 14) + 40
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)
    if pill:
        draw.rounded_rectangle(
            (4, 4, width - 4, height - 4), radius=22, fill=(15, 19, 18, 165)
        )
    for i, line in enumerate(lines):
        x = (width - draw.textlength(line, font=font)) / 2
        draw.text(
            (x, 17 + i * (size + 14)),
            line,
            font=font,
            fill=color,
            stroke_width=1,
            stroke_fill=(0, 0, 0, 90),
        )
    return image


def render_backgrounds(
    config: dict, scenes: list[dict], materials: list[dict], output: Path
) -> tuple[Path, list[dict]]:
    w, h, fps = config["width"], config["height"], config["fps"]
    transition = float(config.get("transition_seconds", 0.35))
    if transition <= 0 or any(scene["duration"] <= transition for scene in scenes):
        raise ValueError("Transition must be positive and shorter than every scene")
    folder = output / "scenes"
    folder.mkdir(exist_ok=True)
    used, timeline, paths = {}, [], []
    for i, scene in enumerate(scenes):
        item = select_material(scene, materials, used)
        seconds = scene["duration"] + (transition if i < len(scenes) - 1 else 0)
        target = folder / f"{i:02}.mp4"
        print(f"画面 {i + 1}/{len(scenes)}: {item['id']} · {seconds:.2f}s", flush=True)
        filters = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},format=yuv420p"
        command = ["ffmpeg", "-y", "-v", "error"]
        if item["kind"] == "image":
            command += ["-loop", "1", "-i", item["path"]]
            filters = f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},zoompan=z='min(1+on*0.00035,1.12)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps={fps},setsar=1,format=yuv420p"
        else:
            command += [
                "-stream_loop",
                "-1",
                "-ss",
                str(scene.get("source_start", 0)),
                "-i",
                item["path"],
            ]
        filters += ",eq=contrast=1.025:saturation=0.94"
        run(
            command
            + [
                "-t",
                f"{seconds:.6f}",
                "-vf",
                filters,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-threads",
                "2",
                str(target),
            ]
        )
        paths.append(target)
        timeline.append({**scene, "material": item, "render_duration": seconds})
    background = output / "background.mp4"
    if len(paths) == 1:
        import shutil

        shutil.copyfile(paths[0], background)
    else:
        command = ["ffmpeg", "-y", "-v", "error", "-filter_complex_threads", "2"]
        for path in paths:
            command += ["-i", str(path)]
        graph = [
            f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]" for i in range(len(paths))
        ]
        last = "v0"
        for i in range(1, len(paths)):
            style = scenes[i - 1].get("transition", "fade")
            if style not in {
                "fade",
                "slideleft",
                "slideright",
                "wipeleft",
                "wiperight",
                "circleopen",
                "dissolve",
            }:
                raise ValueError(f"Unsupported transition: {style}")
            label = f"mix{i}"
            graph.append(
                f"[{last}][v{i}]xfade=transition={style}:duration={transition}:offset={scenes[i]['start']:.6f}[{label}]"
            )
            last = label
        run(
            command
            + [
                "-filter_complex",
                ";".join(graph),
                "-map",
                f"[{last}]",
                "-t",
                str(sum(s["duration"] for s in scenes)),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-threads",
                "2",
                "-pix_fmt",
                "yuv420p",
                str(background),
            ]
        )
    write_json(
        output / "timeline.json",
        {
            "title": config["title"],
            "matching": "catalog keyword tags with repetition penalty",
            "transition_seconds": transition,
            "scenes": timeline,
        },
    )
    return background, timeline


def compose(
    config: dict,
    background: Path,
    scenes: list[dict],
    cues: list[dict],
    narration: Path,
    materials: list[dict],
    output: Path,
    *,
    target_name: str = "final.mp4",
) -> Path:
    from moviepy import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        VideoClip,
        VideoFileClip,
        afx,
        vfx,
    )

    w, h, fps = config["width"], config["height"], config["fps"]
    total = duration(narration)
    base = VideoFileClip(str(background)).without_audio()
    # Explicitly pad a rounded last video frame so audio is never cut short.
    base = base.with_effects(
        [vfx.Freeze(t="end", freeze_duration=max(0, total - base.duration))]
    ).with_duration(total)
    layers, resources = [base], [base]
    shade = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        shade[y, :, 3] = round(
            max(
                max(0, 1 - y / (h * 0.30)) * 170,
                max(0, (y - h * 0.58) / (h * 0.42)) * 215,
            )
        )
    layers.append(ImageClip(shade).with_duration(total))

    def text_layer(text, size, y, start=0, seconds=total, color="#fff8e7", pill=False):
        image = make_text(text, int(w * 0.88), size, color=color, pill=pill)
        clip = (
            ImageClip(np.array(image))
            .with_start(start)
            .with_duration(seconds)
            .with_position(("center", y))
        )
        layers.append(clip)

    text_layer(
        config.get("brand", "V I D E O  /  N O T E S"),
        round(w * 0.026),
        round(h * 0.037),
        color="#e6c990",
    )
    text_layer(
        config.get("subtitle", "MATERIALS / VOICE / CAPTIONS"),
        round(w * 0.019),
        round(h * 0.082),
    )
    title = config["title"].replace("，", "，\n", 1)
    text_layer(
        title,
        round(w * 0.074),
        round(h * 0.13),
        seconds=min(4.8, scenes[0]["duration"]),
    )
    for i, scene in enumerate(scenes):
        start, seconds = scene["start"], scene["duration"]
        if i:
            text_layer(
                scene["label"], round(w * 0.047), round(h * 0.14), start, seconds
            )
        text_layer(
            f"{i + 1:02}  /  {len(scenes):02}",
            round(w * 0.026),
            round(h * 0.9),
            start,
            seconds,
            color="#e6c990",
        )
        sticker = next(
            (
                item
                for item in materials
                if item["kind"] == "sticker" and item["id"] == scene.get("sticker")
            ),
            None,
        )
        if sticker:
            with Image.open(sticker["path"]) as sticker_image:
                sticker_pixels = np.array(sticker_image.convert("RGBA"))
            clip = (
                ImageClip(sticker_pixels)
                .resized(width=round(w * 0.13))
                .with_duration(max(0.1, seconds - 0.6))
            )
            clip = clip.with_effects(
                [
                    vfx.Resize(lambda t: 1 + 0.07 * math.sin(t * 3)),
                    vfx.CrossFadeIn(0.18),
                ]
            )
            clip = clip.with_position(
                lambda t: (round(w * 0.78), round(h * 0.255 + 10 * math.sin(t * 2)))
            ).with_start(start + 0.35)
            layers.append(clip)
    for cue in cues:
        text_layer(
            cue["text"],
            round(w * 0.050),
            round(h * 0.785),
            cue["start"],
            cue["end"] - cue["start"],
            pill=True,
        )
    text_layer(
        config.get("footer", "VIDEO NOTES"),
        round(w * 0.021),
        round(h * 0.947),
        seconds=max(0, total - 3),
        color="#d9d1c5",
    )
    text_layer(
        "ICONS: TWITTER & CONTRIBUTORS · CC BY 4.0",
        round(w * 0.017),
        round(h * 0.947),
        start=max(0, total - 3),
        seconds=min(3, total),
        color="#d9d1c5",
    )
    progress = ImageClip(
        np.full((4, w, 3), [230, 201, 144], dtype=np.uint8)
    ).with_duration(total)
    progress_mask = VideoClip(
        lambda t: np.tile((np.arange(w) < w * min(1, t / total)).astype(float), (4, 1)),
        is_mask=True,
        duration=total,
    )
    progress = progress.with_mask(progress_mask).with_position((0, h - 4))
    layers.append(progress)
    voice = AudioFileClip(str(narration))
    resources.append(voice)
    audio_layers = [voice]
    music = next((m for m in materials if m["kind"] == "music"), None)
    if music:
        track = AudioFileClip(music["path"])
        resources.append(track)
        track = track.with_effects(
            [
                afx.AudioLoop(duration=total),
                afx.MultiplyVolume(config.get("music_volume", 0.10)),
                afx.AudioFadeIn(0.8),
                afx.AudioFadeOut(1.2),
            ]
        )
        audio_layers.append(track)
    final = (
        CompositeVideoClip(layers, size=(w, h))
        .with_audio(CompositeAudioClip(audio_layers))
        .with_duration(total)
    )
    target = output / target_name
    print(f"合成字幕、动态贴纸和音轨: {total:.2f}s", flush=True)
    try:
        final.write_videofile(
            str(target),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            preset="fast",
            threads=4,
            ffmpeg_params=[
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-color_primaries",
                "bt709",
                "-color_trc",
                "bt709",
                "-colorspace",
                "bt709",
            ],
            logger="bar",
        )
    finally:
        final.close()
        for resource in resources:
            resource.close()
    normalized = output / "final-normalized.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(target),
            "-map",
            "0:v",
            "-map",
            "0:a",
            "-c:v",
            "copy",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar",
            "48000",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            str(total),
            "-movflags",
            "+faststart",
            str(normalized),
        ]
    )
    normalized.replace(target)
    return target


def inspect_output(video: Path, output: Path, expected_duration: float) -> dict:
    info = probe(video)
    video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio_stream = next(s for s in info["streams"] if s["codec_type"] == "audio")
    actual = float(info["format"]["duration"])
    video_seconds = float(video_stream.get("duration", actual))
    audio_seconds = float(audio_stream.get("duration", actual))
    av_delta = abs(video_seconds - audio_seconds)
    if av_delta > 0.15:
        raise RuntimeError(f"Video/audio tracks differ by {av_delta:.3f}s")
    if abs(actual - expected_duration) > 0.2:
        raise RuntimeError(
            f"Audio/video duration mismatch: {actual} vs {expected_duration}"
        )
    # Full decode catches errors that reading the container header misses.
    run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"])
    thumb_dir = output / "qa"
    thumb_dir.mkdir(exist_ok=True)
    frames = []
    frame_rate = float(Fraction(video_stream.get("avg_frame_rate") or "24/1")) or 24
    last_sample = max(0, min(actual, video_seconds) - max(0.2, 1 / frame_rate) - 1e-6)
    for i in range(6):
        # PNG avoids FFmpeg 9's stricter limited-range MJPEG encoder checks.
        target = thumb_dir / f"frame-{i}.png"
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                str(min(last_sample, actual * (i + 0.5) / 6)),
                "-i",
                str(video),
                "-frames:v",
                "1",
                str(target),
            ]
        )
        with Image.open(target) as frame:
            frames.append(ImageOps.pad(frame.convert("RGB"), (240, 427),
                                       Image.Resampling.LANCZOS, color="#111"))
    sheet = Image.new("RGB", (240 * 3, 427 * 2), "#111")
    for i, frame in enumerate(frames):
        sheet.paste(frame, ((i % 3) * 240, (i // 3) * 427))
    sheet.save(output / "contact-sheet.jpg", quality=90)
    report = {
        "duration_seconds": actual,
        "width": video_stream["width"],
        "height": video_stream["height"],
        "video_codec": video_stream["codec_name"],
        "audio_codec": audio_stream["codec_name"],
        "video_duration": video_seconds,
        "audio_duration": audio_seconds,
        "av_delta_seconds": av_delta,
        "full_decode": "passed",
        "bytes": video.stat().st_size,
    }
    write_json(output / "verification.json", report)
    return report
