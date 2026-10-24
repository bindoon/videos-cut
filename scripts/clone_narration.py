"""Generate reference-conditioned speech with F5-TTS MLX, entirely locally."""

import argparse
import hashlib
import json
import re
import subprocess
import time
import wave
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from f5_tts_mlx.cfm import F5TTS
    from f5_tts_mlx.dit import DiT
    from f5_tts_mlx.utils import convert_char_to_pinyin
    from mlx import nn
    from vocos_mlx import Vocos

    # F5 0.2.6 passes MLX scalar durations into random.normal's shape.
    # MLX 0.32 requires Python integers. Adapt only this isolated process;
    # keep installed upstream files untouched.
    original_normal = mx.random.normal

    def integer_shape_normal(shape=(), *args, **kwargs):
        shape = tuple(int(d.item()) if hasattr(d, "item") else int(d) for d in shape)
        return original_normal(shape, *args, **kwargs)

    mx.random.normal = integer_shape_normal

    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    output = Path(request["output"])
    output.mkdir(parents=True, exist_ok=True)
    reference = Path(request["reference_audio"])
    model_path = Path(request["model_path"])
    vocoder_path = Path(request["vocoder_path"])
    weight_file = model_path / "model_v1_4b.safetensors"
    settings = {
        "reference_sha256": digest(reference),
        "reference_text": request["reference_text"],
        "model_sha256": digest(weight_file),
        "vocoder_sha256": digest(vocoder_path / "model.safetensors"),
        "steps": 32,
        "method": "euler",
        "cfg": 2.0,
        "seed": 20261024,
        "loudness_target_lufs": -18,
        "engine": "f5-tts-mlx/0.2.6",
    }
    cache_key = hashlib.sha256(
        json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]
    manifest = output / "clone-manifest.json"
    texts = list(
        dict.fromkeys(
            line for scene in request["config"]["scenes"] for line in scene["lines"]
        )
    )
    records = []
    if manifest.exists():
        previous = json.loads(manifest.read_text())
        if previous.get("cache_key") == cache_key:
            records = [
                r
                for r in previous["utterances"]
                if Path(r["path"]).is_file() and digest(Path(r["path"])) == r["sha256"]
            ]
    done = {r["text"]: r for r in records}
    if all(t in done for t in texts):
        print("All cloned utterances cached", flush=True)
        return
    print("Load local F5-TTS + Vocos models", flush=True)
    # Same public architecture/loading recipe as F5TTS.from_pretrained, with
    # explicit local paths and duration estimation (no hidden model downloads).
    vocab = {
        v: i for i, v in enumerate((model_path / "vocab.txt").read_text().split("\n"))
    }
    vocos = Vocos.from_pretrained(str(vocoder_path))
    model = F5TTS(
        transformer=DiT(
            dim=1024,
            depth=22,
            heads=16,
            ff_mult=2,
            text_dim=512,
            conv_layers=4,
            text_num_embeds=len(vocab) - 1,
            text_mask_padding=True,
        ),
        vocab_char_map=vocab,
        vocoder=vocos.decode,
    )
    nn.quantize(
        model,
        bits=4,
        class_predicate=lambda path, module: (
            isinstance(module, nn.Linear) and module.weight.shape[1] % 64 == 0
        ),
    )
    model.load_weights(list(mx.load(str(weight_file)).items()))
    mx.eval(model.parameters())
    model.eval()
    rate = 24000
    prepared = output / "reference-f5.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(reference),
            "-ac",
            "1",
            "-ar",
            str(rate),
            "-af",
            "highpass=f=60",
            "-c:a",
            "pcm_s16le",
            str(prepared),
        ],
        check=True,
        timeout=60,
    )
    reference_pcm, actual_rate = sf.read(prepared, dtype="float32")
    if actual_rate != rate:
        raise ValueError("Reference sample rate mismatch")
    reference_mlx = mx.array(reference_pcm)
    rms = mx.sqrt(mx.mean(mx.square(reference_mlx))).item()
    if 0 < rms < 0.1:
        reference_mlx = reference_mlx * (0.1 / rms)
    reference_frames = len(reference_pcm) // 256

    def text_size(text):
        return len(text.encode("utf8")) + 3 * len(re.findall(r"。，、；：？！", text))

    for i, text in enumerate(texts):
        if text in done:
            continue
        started = time.monotonic()
        print(f"Clone {i + 1}/{len(texts)}: {text}", flush=True)
        frames = reference_frames + max(
            94,
            round(
                reference_frames
                * text_size(text)
                / text_size(request["reference_text"])
            ),
        )
        phonemes = convert_char_to_pinyin([request["reference_text"] + " " + text])
        result, _ = model.sample(
            reference_mlx[None, :],
            text=phonemes,
            duration=frames,
            steps=32,
            method="euler",
            cfg_strength=2.0,
            sway_sampling_coef=-1.0,
            seed=20261024 + i,
        )
        generated = result.reshape(-1)[len(reference_pcm) :]
        mx.eval(generated)
        generated = np.asarray(generated, dtype=np.float32).reshape(-1)
        seconds = len(generated) / rate
        if not 0.3 < seconds < max(16, len(text) / 2):
            raise RuntimeError(f"Unexpected utterance duration: {seconds}")
        peak = float(np.max(np.abs(generated)))
        if peak > 0.98:
            generated = generated * (0.98 / peak)
        native = output / f"f5-{i:02}-native.wav"
        target = output / f"f5-{i:02}-{cache_key}.wav"
        sf.write(native, generated, rate, subtype="PCM_16")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
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
        native.unlink()
        with wave.open(str(target), "rb") as audio:
            seconds = audio.getnframes() / audio.getframerate()
        record = {
            "text": text,
            "path": str(target.resolve()),
            "duration_seconds": seconds,
            "sample_rate": 48000,
            "seed": 20261024 + i,
            "sha256": digest(target),
            "generation_seconds": round(time.monotonic() - started, 3),
        }
        records.append(record)
        done[text] = record
        manifest.write_text(
            json.dumps(
                {
                    "provider": "F5-TTS-MLX-v1-4bit",
                    "cache_key": cache_key,
                    **settings,
                    "reference_audio": str(reference.resolve()),
                    "utterances": records,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(
            f"Generated {seconds:.2f}s in {record['generation_seconds']:.2f}s",
            flush=True,
        )
        mx.clear_cache()


if __name__ == "__main__":
    main()
