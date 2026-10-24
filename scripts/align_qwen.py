"""Isolated, cached Qwen3 forced alignment of the supplied narration script."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

SCHEMA = "qwen-forced-v1"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    request = json.loads(parser.parse_args().request.read_text())
    root = Path(request["model"])
    assets = {
        p.name: sha(p)
        for p in sorted(root.iterdir())
        if p.suffix in {".json", ".txt", ".safetensors"} and p.name != "source.json"
    }
    fingerprint = hashlib.sha256(
        json.dumps(assets, sort_keys=True).encode()
    ).hexdigest()
    model, records = None, []
    for item in request["utterances"]:
        text, path = item["expected"], Path(item["path"])
        checksum = sha(path)
        key = hashlib.sha256(
            (SCHEMA + fingerprint + checksum + text).encode()
        ).hexdigest()
        cache = root / "alignment-cache" / f"{key}.json"
        if cache.exists():
            records.append(json.loads(cache.read_text()))
            print(f"Qwen 对齐缓存: {text}", flush=True)
            continue
        if model is None:
            print("加载 Qwen 对齐运行库", flush=True)
            import torch
            from qwen_asr import Qwen3ForcedAligner

            torch.set_num_threads(4)
            print("加载本地 Qwen 权重", flush=True)
            model = Qwen3ForcedAligner.from_pretrained(
                str(root.resolve()),
                device_map="cpu",
                dtype=torch.float32,
                attn_implementation="sdpa",
                local_files_only=True,
            )
        audio = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "f32le",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        )
        waveform = np.frombuffer(audio.stdout, dtype="<f4").copy()
        aligned = model.align(audio=(waveform, 16000), text=text, language="Chinese")[0]
        record = {
            "expected": text,
            "audio_sha256": checksum,
            "words": [
                {"text": x.text, "start": x.start_time, "end": x.end_time}
                for x in aligned
            ],
        }
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        records.append(record)
        print(f"Qwen 逐字对齐: {text}", flush=True)
    report = {
        "schema": SCHEMA,
        "model_sha256": fingerprint,
        "model_assets_sha256": assets,
        "runtime": "qwen-asr==0.0.6; CPU float32",
        "model_revision": json.loads((root / "source.json").read_text())["sha"],
        "utterances": records,
    }
    Path(request["output"]).write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
