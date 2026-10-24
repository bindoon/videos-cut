"""Generate narration with official IndexTTS 2.5 in its isolated runtime."""

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import wave
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def key_for(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def write_manifest(path, data):
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    config = request["config"]
    options = config.get("index_tts", {})
    model_path = Path(request["model_path"])
    upstream = Path(request["upstream_path"])
    output = Path(request["output"])
    output.mkdir(parents=True, exist_ok=True)
    reference = Path(request["reference_audio"])
    upstream_revision = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    weight_paths = [
        "gpt.pth",
        "codec.pth",
        "s2mel.pth",
        "feat1.pt",
        "feat2.pt",
        "wav2vec2bert_stats.pt",
        "config.yaml",
        "multilingual_zh_ja_yue_char_del.tiktoken",
        "hf_cache/w2v-bert-2.0/model.safetensors",
        "hf_cache/w2v-bert-2.0/config.json",
        "hf_cache/w2v-bert-2.0/preprocessor_config.json",
        "hf_cache/campplus_cn_common.bin",
        "hf_cache/bigvgan/config.json",
        "hf_cache/bigvgan/bigvgan_generator.pt",
    ]
    print("Check local model and reference digests", flush=True)
    hashes = {name: digest(model_path / name) for name in weight_paths}
    settings = {
        "provider": "IndexTTS-2.5",
        "reference_audio": str(reference.resolve()),
        "reference_sha256": digest(reference),
        "model_sha256": hashes["gpt.pth"],
        "model_revision": json.loads((model_path / "source.json").read_text())["sha"],
        "model_assets_sha256": hashes,
        "upstream_revision": upstream_revision,
        "device": request.get("device", "mps"),
        "engine": "official-pytorch/48k-narration-v1",
        "output_sample_rate": 48000,
        "loudness_target_lufs": -18,
        "do_sample": True,
        "num_beams": 1,
        "max_mel_tokens": 350,
    }
    cache_key = key_for(settings)
    settings["cache_key"] = cache_key
    manifest = output / "index-manifest.json"
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    records = (
        previous.get("utterances", []) if previous.get("cache_key") == cache_key else []
    )
    texts = list(
        dict.fromkeys(line for scene in config["scenes"] for line in scene["lines"])
    )
    jobs = []
    for i, text in enumerate(texts):
        controls = {
            "seed": int(options.get("seed", 20261024)) + i,
            "duration_factor": float(options.get("duration_factor", 1.0)),
            "emo_vector": options.get("emo_vector"),
        }
        override = options.get("line_overrides", {}).get(text, {})
        if set(override) - set(controls) - {"tts_text"}:
            raise ValueError("Unknown IndexTTS line control")
        controls.update(override)
        if "tts_text" in controls and (
            not isinstance(controls["tts_text"], str)
            or not controls["tts_text"].strip()
        ):
            raise ValueError(
                "tts_text must be non-empty text or native pronunciation annotations"
            )
        if not 0.5 <= controls["duration_factor"] <= 2:
            raise ValueError("duration_factor must be 0.5 to 2")
        vector = controls["emo_vector"]
        if vector is not None and (
            len(vector) != 8 or any(not 0 <= v <= 1 for v in vector)
        ):
            raise ValueError("emo_vector requires eight values from 0 to 1")
        line_key = key_for({"settings": cache_key, "text": text, "controls": controls})
        cached = next(
            (
                r
                for r in records
                if r["text"] == text
                and r["cache_key"] == line_key
                and Path(r["path"]).is_file()
                and digest(Path(r["path"])) == r["sha256"]
            ),
            None,
        )
        jobs.append((i, text, controls, line_key, cached))
    if all(job[-1] for job in jobs):
        print("All IndexTTS utterances cached", flush=True)
        return
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    sys.path.insert(0, str(upstream.resolve()))
    import numpy as np
    import soundfile as sf
    import torch
    from indextts.infer_v2_5 import IndexTTS2

    torch.set_num_threads(4)
    prepared = output / f"reference-{settings['reference_sha256'][:16]}.wav"
    if not prepared.exists():
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(reference),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(prepared),
            ],
            check=True,
            timeout=60,
        )
    print("Load official IndexTTS 2.5 on " + settings["device"], flush=True)
    engine = IndexTTS2(
        cfg_path=str(model_path / "config.yaml"),
        model_dir=str(model_path),
        device=settings["device"],
        use_bf16=False,
        use_cuda_kernel=False,
        use_qwen_emo=False,
    )
    for i, text, controls, line_key, cached in jobs:
        if cached:
            continue
        started = time.monotonic()
        print(f"NARRATION {i + 1}/{len(jobs)}: {text}", flush=True)
        random.seed(controls["seed"])
        np.random.seed(controls["seed"])
        torch.manual_seed(controls["seed"])
        native = output / f"index-{i:02}-{line_key}-{time.time_ns()}-native.wav"
        target = output / f"index-{i:02}-{line_key}.wav"
        if target.exists():
            raise FileExistsError(
                "Refusing to replace an unverified narration segment: " + str(target)
            )
        engine.infer(
            spk_audio_prompt=str(prepared),
            text=controls.get("tts_text", text),
            lang="ZH",
            output_path=str(native),
            use_random=False,
            do_sample=True,
            num_beams=1,
            max_mel_tokens=350,
            verbose=False,
            duration_factor=controls["duration_factor"],
            emo_vector=controls["emo_vector"],
        )
        pcm, rate = sf.read(native, dtype="float32")
        if rate != 22050 or not np.isfinite(pcm).all() or np.max(np.abs(pcm)) < 0.001:
            raise ValueError("Invalid generated speech")
        if not 0.3 < len(pcm) / rate < max(20, len(text)):
            raise ValueError("Unexpected generated speech duration")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(native),
                "-ac",
                "1",
                "-ar",
                "48000",
                "-af",
                "loudnorm=I=-18:TP=-2:LRA=9",
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            check=True,
            timeout=60,
        )
        with wave.open(str(target), "rb") as audio:
            seconds = audio.getnframes() / audio.getframerate()
            assert (
                audio.getnchannels(),
                audio.getsampwidth(),
                audio.getframerate(),
            ) == (1, 2, 48000)
        record = {
            "text": text,
            "path": str(target.resolve()),
            "native_path": str(native.resolve()),
            "duration_seconds": seconds,
            "sample_rate": 48000,
            "controls": controls,
            "cache_key": line_key,
            "sha256": digest(target),
            "generation_seconds": round(time.monotonic() - started, 3),
        }
        records = [r for r in records if r["text"] != text] + [record]
        write_manifest(
            manifest,
            {
                **settings,
                "utterances": sorted(records, key=lambda r: texts.index(r["text"])),
            },
        )
        print("SAVED " + json.dumps(record, ensure_ascii=False), flush=True)
        if settings["device"] == "mps":
            torch.mps.empty_cache()


if __name__ == "__main__":
    main()
