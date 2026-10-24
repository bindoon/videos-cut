"""Align a supplied Chinese script to audio using CTC, without free transcription.

Uses the Chinese acoustic model selected by WhisperX, through the installed
transformers / torchaudio APIs. No WhisperX or diarization dependency is needed.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import torch
import torchaudio.functional as audio_functions
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

ENGINE = "ctc-forced-v1"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    folder = Path(request["model"])
    output = Path(request["output"])
    model_digest = digest(folder / "pytorch_model.bin")
    vocab = json.loads((folder / "vocab.json").read_text())
    extractor = Wav2Vec2FeatureExtractor.from_pretrained(folder, local_files_only=True)
    torch.set_num_threads(4)
    model = Wav2Vec2ForCTC.from_pretrained(folder, local_files_only=True).eval()
    records = []
    for item in request["utterances"]:
        text, path = item["expected"], Path(item["path"])
        checksum = digest(path)
        key = hashlib.sha256(
            (ENGINE + model_digest + checksum + text).encode()
        ).hexdigest()
        cache = folder / "alignment-cache" / f"{key}.json"
        if cache.exists():
            records.append(json.loads(cache.read_text()))
            print(f"CTC 对齐缓存: {text}", flush=True)
            continue
        decoded = subprocess.run(
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
        waveform = np.frombuffer(decoded.stdout, dtype="<f4").copy()
        inputs = extractor(waveform, sampling_rate=16000, return_tensors="pt")
        with torch.inference_mode():
            logits = model(**inputs).logits.cpu()
        # Unknown script characters remain in sequence as acoustic wildcards;
        # they are explicitly marked, never silently deleted or interpolated.
        blank = model.config.pad_token_id
        chars = [c for c in text if c.isalnum()]
        wildcard = logits.shape[-1]
        wildcard_logits = logits[:, :, 1:].max(dim=-1, keepdim=True).values
        emission = torch.cat([logits, wildcard_logits], dim=-1).log_softmax(-1)
        target = torch.tensor([[vocab.get(c.lower(), wildcard) for c in chars]])
        aligned, scores = audio_functions.forced_align(emission, target, blank=blank)
        spans = audio_functions.merge_tokens(aligned[0], scores[0].exp(), blank=blank)
        if len(spans) != len(chars):
            raise ValueError(f"Incomplete CTC alignment: {text}")
        # Convolution centers are at sample 199.5 + 320 * frame, not at zero.
        stride = int(np.prod(model.config.conv_stride))
        receptive, jump = 1, 1
        for kernel, step in zip(model.config.conv_kernel, model.config.conv_stride):
            receptive += (kernel - 1) * jump
            jump *= step
        words = []
        for char, span in zip(chars, spans):
            words.append(
                {
                    "text": char,
                    "start": (span.start * stride + (receptive - 1) / 2) / 16000,
                    "end": (span.end * stride + (receptive - 1) / 2) / 16000,
                    "score": span.score,
                    "wildcard": char.lower() not in vocab,
                }
            )
        reverse = {v: k for k, v in vocab.items()}
        greedy = torch.unique_consecutive(logits[0].argmax(-1)).tolist()
        record = {
            "expected": text,
            "audio_sha256": checksum,
            "words": words,
            "greedy_transcript": "".join(
                reverse.get(t, "") for t in greedy if t != blank
            ),
            "mean_score": float(
                np.mean([w["score"] for w in words if not w["wildcard"]])
            ),
            "wildcard_count": sum(w["wildcard"] for w in words),
        }
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        records.append(record)
        print(f"CTC 逐字对齐: {text} (score={record['mean_score']:.3f})", flush=True)
    report = {
        "schema": ENGINE,
        "model": str(folder.resolve()),
        "model_sha256": model_digest,
        "model_revision": json.loads((folder / "source.json").read_text())["sha"],
        "utterances": records,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
