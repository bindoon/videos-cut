"""Fetch a pinned public MLX voice model with checked, resumable HTTP ranges."""

import argparse
import fnmatch
import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def verify_small_file(blob, item):
    expected = item.get("lfs", {}).get("sha256")
    if expected:
        actual = hashlib.sha256(blob).hexdigest()
    else:
        expected = item.get("blobId")
        actual = hashlib.sha1(f"blob {len(blob)}\0".encode() + blob).hexdigest()
    if expected and actual != expected:
        raise ValueError(f"File digest mismatch: {item['rfilename']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include", nargs="+", required=True)
    parser.add_argument(
        "--mirror-repo-url",
        help="Optional resolve/master mirror; large files must match pinned HF LFS hashes",
    )
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    metadata = root / "source.json"
    if metadata.exists():
        data = json.loads(metadata.read_text())
        if data.get("id") != args.repo:
            raise ValueError("Output directory belongs to another model repository")
    else:
        for attempt in range(4):
            try:
                data = json.load(
                    urllib.request.urlopen(
                        f"https://huggingface.co/api/models/{args.repo}?blobs=true",
                        timeout=60,
                    )
                )
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)
        metadata.write_text(json.dumps(data, indent=2))
    revision = data["sha"]
    files = [f for f in data["siblings"] if not f["rfilename"].startswith(".")]
    if args.include:
        files = [
            f
            for f in files
            if any(fnmatch.fnmatch(f["rfilename"], pattern) for pattern in args.include)
        ]

    def fetch_file(item):
        name = item["rfilename"]
        target = root / name
        size = item["size"]
        if target.exists() and target.stat().st_size == size:
            if size < 10_000_000:
                verify_small_file(target.read_bytes(), item)
                return
            expected = item.get("lfs", {}).get("sha256")
            if expected:
                with target.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if actual != expected:
                    raise ValueError(f"Cached model SHA-256 mismatch: {name}")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        url = (
            f"{args.mirror_repo_url.rstrip('/')}/resolve/master/{name}"
            if args.mirror_repo_url
            else f"https://huggingface.co/{args.repo}/resolve/{revision}/{name}"
        )
        if size < 10_000_000:
            with urllib.request.urlopen(url, timeout=90) as response:
                blob = response.read()
            if len(blob) != size:
                raise ValueError(f"Short download: {name}")
            verify_small_file(blob, item)
            target.write_bytes(blob)
            print("Downloaded", name, size, flush=True)
            return
        parts = root / ".parts"
        parts.mkdir(exist_ok=True)
        count = 16
        chunk = (size + count - 1) // count

        def fetch_part(i):
            start = i * chunk
            end = min(size - 1, start + chunk - 1)
            path = parts / f"{name}.{i:02}"
            for attempt in range(4):
                already = path.stat().st_size if path.exists() else 0
                if already == end - start + 1:
                    return path
                offset = start + already
                try:
                    request = urllib.request.Request(
                        url, headers={"Range": f"bytes={offset}-{end}"}
                    )
                    with urllib.request.urlopen(request, timeout=90) as response:
                        content_range = response.headers.get("Content-Range", "")
                        if response.status != 206 or not content_range.startswith(
                            f"bytes {offset}-{end}/"
                        ):
                            raise ValueError(f"Invalid range: {content_range}")
                        with path.open("ab") as stream:
                            while block := response.read(262144):
                                stream.write(block)
                    if path.stat().st_size != end - start + 1:
                        raise ValueError("Truncated model part")
                    print(f"Model part {i + 1}/{count} complete", flush=True)
                    return path
                except Exception:
                    if attempt == 3:
                        raise
            raise RuntimeError("Download did not complete")

        with ThreadPoolExecutor(max_workers=16) as pool:
            chunks = list(pool.map(fetch_part, range(count)))
        temporary = target.with_suffix(".part")
        with temporary.open("wb") as stream:
            for path in chunks:
                with path.open("rb") as part:
                    while block := part.read(1024 * 1024):
                        stream.write(block)
        expected = item.get("lfs", {}).get("sha256")
        with temporary.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if expected and actual != expected:
            raise ValueError("Model SHA-256 mismatch")
        temporary.replace(target)
        for path in chunks:
            path.unlink()
        print("Verified", name, actual, flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch_file, files))
    print("Model ready:", root.resolve(), flush=True)


if __name__ == "__main__":
    main()
