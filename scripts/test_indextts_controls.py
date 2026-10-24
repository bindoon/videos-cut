"""Run isolated, reproducible short-utterance tests of official IndexTTS 2.5."""

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compile_ssml(source):
    """A deliberately small adapter; unsupported tags raise, never disappear."""
    root = ET.fromstring(source)
    if root.tag != "speak":
        raise ValueError("SSML root must be speak")
    if root.attrib:
        raise ValueError("speak attributes are unsupported in this experiment")
    parts = []

    def text(value):
        if not value:
            return
        if parts and "text" in parts[-1]:
            parts[-1]["text"] += value
        else:
            parts.append({"text": value})

    text(root.text)
    for node in root:
        supported_attributes = {
            "break": {"time"},
            "phoneme": {"alphabet", "ph"},
            "sub": {"alias"},
        }
        if set(node.attrib) - supported_attributes.get(node.tag, set()):
            raise ValueError(f"Unsupported SSML attributes on {node.tag}")
        if list(node):
            raise ValueError("Nested SSML is unsupported in this experiment")
        if node.tag == "break":
            match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s)", node.attrib["time"])
            if not match:
                raise ValueError("Invalid break duration")
            seconds = float(match[1]) / (1000 if match[2] == "ms" else 1)
            if not 0 <= seconds <= 10:
                raise ValueError("Break must be between 0 and 10 seconds")
            parts.append({"pause_seconds": seconds})
        elif node.tag == "phoneme" and node.get("alphabet") == "py":
            chars, phonemes = node.text or "", node.attrib["ph"].split()
            if len(chars) != len(phonemes) or not all(
                re.fullmatch(r"[a-zA-ZüÜvV]+[1-5]", p) for p in phonemes
            ):
                raise ValueError(
                    "Pinyin must provide one tone-marked syllable per character"
                )
            text("".join(f"<{c}|{p.upper()}>" for c, p in zip(chars, phonemes)))
        elif node.tag == "sub":
            text(node.attrib["alias"])
        else:
            raise ValueError(f"Unsupported SSML tag: {node.tag}")
        text(node.tail)
    return [p for p in parts if "text" not in p or p["text"].strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument(
        "--model", type=Path, default=Path("assets/models/IndexTTS-2.5")
    )
    parser.add_argument(
        "--upstream", type=Path, default=Path("upstream/index-tts-reference")
    )
    parser.add_argument("--device", default="mps")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.upstream.resolve()))
    import numpy as np
    import soundfile as sf
    import torch
    from indextts.infer_v2_5 import IndexTTS2

    reference = args.output / "reference-24k.wav"
    if not reference.exists():
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(args.reference),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(reference),
            ],
            check=True,
        )
    torch.set_num_threads(4)
    engine = IndexTTS2(
        cfg_path=str((args.model / "config.yaml").resolve()),
        model_dir=str(args.model.resolve()),
        device=args.device,
        use_bf16=False,
        use_cuda_kernel=False,
        use_qwen_emo=False,
    )
    coffee = "喜欢清爽，就喝一口黑咖啡。"
    cases = [
        {"id": "01-coffee-default", "label": "原速 / 默认情绪", "text": coffee},
        {
            "id": "02-coffee-faster",
            "label": "目标时长系数 0.85",
            "text": coffee,
            "duration_factor": 0.85,
        },
        {
            "id": "03-coffee-happy",
            "label": "高兴情绪向量 0.8",
            "text": coffee,
            "emo_vector": [0.8, 0, 0, 0, 0, 0, 0, 0],
        },
        {
            "id": "04-coffee-calm",
            "label": "平静情绪向量 0.8",
            "text": coffee,
            "emo_vector": [0, 0, 0, 0, 0, 0, 0, 0.8],
        },
        {
            "id": "05-pronunciation-hang",
            "label": "强制读 hang2",
            "text": "这个字读<行|HANG2>。",
            "ssml": '<speak>这个字读<phoneme alphabet="py" ph="hang2">行</phoneme>。</speak>',
            "display_text": "这个字读行。",
        },
        {
            "id": "06-pronunciation-xing",
            "label": "强制读 xing2",
            "text": "这个字读<行|XING2>。",
            "ssml": '<speak>这个字读<phoneme alphabet="py" ph="xing2">行</phoneme>。</speak>',
            "display_text": "这个字读行。",
        },
        {
            "id": "07-ssml-pause-500ms",
            "label": "XML 适配层插入 500ms 静音",
            "text": coffee,
            "ssml": '<speak>喜欢清爽<break time="500ms"/>就喝一口黑咖啡。</speak>',
        },
    ]
    manifest_path = args.output / "manifest.json"
    records = []
    revision = subprocess.check_output(
        ["git", "-C", str(args.upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    common = {
        "engine": "IndexTTS-2.5 official PyTorch",
        "upstream_revision": revision,
        "device": args.device,
        "reference": str(args.reference.resolve()),
        "reference_sha256": sha256(args.reference),
        "model_revision": json.loads((args.model / "source.json").read_text())["sha"],
        "seed": 20261024,
        "do_sample": True,
        "num_beams": 1,
        "max_mel_tokens": 350,
        "ssml_adapter": "experiment-v1: speak, break/time, phoneme/py, sub/alias",
    }
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous.get("settings") != common:
            raise ValueError(
                "Existing output belongs to different settings; use a new output directory"
            )
        records = previous["cases"]
    done = {r["id"]: r for r in records}
    for case in cases:
        target = args.output / (case["id"] + ".wav")
        if (
            case["id"] in done
            and all(done[case["id"]].get(k) == v for k, v in case.items())
            and target.exists()
            and sha256(target) == done[case["id"]]["sha256"]
        ):
            continue
        if target.exists():
            raise FileExistsError(
                f"Refusing to replace an unverified test output: {target}"
            )
        random.seed(common["seed"])
        np.random.seed(common["seed"])
        torch.manual_seed(common["seed"])
        print("TEST", case["id"], case["label"], flush=True)
        started = time.monotonic()
        controls = {
            k: v for k, v in case.items() if k in ("duration_factor", "emo_vector")
        }
        parts = (
            compile_ssml(case["ssml"]) if "ssml" in case else [{"text": case["text"]}]
        )
        samples, adapter_timeline = [], []
        rate = 22050
        for index, part in enumerate(parts):
            start = sum(len(s) for s in samples) / rate
            if "pause_seconds" in part:
                pcm = np.zeros(round(part["pause_seconds"] * rate), dtype=np.float32)
            else:
                fragment = (
                    args.output / f"{case['id']}-part-{index}-{time.time_ns()}.wav"
                )
                engine.infer(
                    spk_audio_prompt=str(reference.resolve()),
                    text=part["text"],
                    lang="ZH",
                    output_path=str(fragment.resolve()),
                    use_random=False,
                    do_sample=True,
                    num_beams=1,
                    max_mel_tokens=350,
                    verbose=True,
                    **controls,
                )
                pcm, actual_rate = sf.read(fragment, dtype="float32")
                if actual_rate != rate:
                    raise ValueError("Unexpected IndexTTS sample rate")
                if len(parts) > 1:
                    # Trim only edges of the separately generated phrases;
                    # never remove silence from inside a word.
                    active = np.flatnonzero(np.abs(pcm) > 0.003)
                    if len(active):
                        pad = round(rate * 0.03)
                        pcm = pcm[
                            max(0, active[0] - pad) : min(
                                len(pcm), active[-1] + pad + 1
                            )
                        ]
            samples.append(pcm)
            adapter_timeline.append(
                {**part, "start": start, "end": start + len(pcm) / rate}
            )
        sf.write(target, np.concatenate(samples), rate, subtype="PCM_16")
        audio, rate = sf.read(target, dtype="float32")
        if not np.isfinite(audio).all() or np.max(np.abs(audio)) < 0.001:
            raise ValueError("Invalid/silent generated speech")
        record = {
            **case,
            "path": str(target.resolve()),
            "duration_seconds": len(audio) / rate,
            "sample_rate": rate,
            "generation_seconds": round(time.monotonic() - started, 3),
            "sha256": sha256(target),
            "adapter_timeline": adapter_timeline,
        }
        records.append(record)
        manifest_path.write_text(
            json.dumps(
                {"settings": common, "cases": records}, ensure_ascii=False, indent=2
            )
        )
        print("SAVED", json.dumps(record, ensure_ascii=False), flush=True)
        if args.device == "mps":
            torch.mps.empty_cache()


if __name__ == "__main__":
    main()
