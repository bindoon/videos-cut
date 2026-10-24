"""Download public CTranslate2 Whisper weights without Hugging Face credentials."""

import argparse
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "model", choices=["tiny", "base", "small"], default="base", nargs="?"
    )
    args = parser.parse_args()
    root = Path("assets/models") / args.model
    root.mkdir(parents=True, exist_ok=True)
    source = f"https://huggingface.co/Systran/faster-whisper-{args.model}"

    def fetch(name):
        dest = root / name
        if not dest.exists():
            print(f"下载 {args.model}/{name}", flush=True)
            request = urllib.request.Request(
                f"{source}/resolve/main/{name}",
                headers={"User-Agent": "videos-cut/0.1"},
            )
            temporary = dest.with_suffix(dest.suffix + ".part")
            with (
                urllib.request.urlopen(request, timeout=90) as response,
                temporary.open("wb") as stream,
            ):
                while chunk := response.read(262144):
                    stream.write(chunk)
            temporary.replace(dest)
            print(
                f"完成 {args.model}/{name}: {dest.stat().st_size:,} bytes", flush=True
            )
        with dest.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        return name, {"bytes": dest.stat().st_size, "sha256": checksum}

    with ThreadPoolExecutor(max_workers=4) as pool:
        files = dict(
            pool.map(
                fetch, ["config.json", "tokenizer.json", "vocabulary.txt", "model.bin"]
            )
        )
    Path(f"docs/asr-{args.model}-lock.json").write_text(
        json.dumps({"source": source, "files": files}, indent=2)
    )


if __name__ == "__main__":
    main()
