"""Fetch the reviewed, pinned Commons files; never silently accept new bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.request

FILM = Path(__file__).resolve().parents[1]


def main() -> None:
    sources = json.loads((FILM / "montage-sources.json").read_text())
    target = FILM / "data/montage"
    target.mkdir(parents=True, exist_ok=True)
    for source in sources:
        destination = target / source["file"]
        expected = source["sha256"]
        if destination.exists():
            digest = hashlib.file_digest(destination.open("rb"), "sha256").hexdigest()
            if digest != expected:
                raise ValueError(f"Changed cached material: {destination}; inspect before replacing")
            print("CACHED", source["id"], flush=True)
            continue
        request = urllib.request.Request(source["url"], headers={
            "User-Agent": "HangzhouFilmBot/1.0 (https://github.com/bindoon/videos-cut)",
        })
        temporary = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as stream:
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > source["bytes"]:
                    raise ValueError(f"Unexpected material size: {source['id']}")
                stream.write(block)
                digest.update(block)
        if count != source["bytes"] or digest.hexdigest() != expected:
            raise ValueError(f"Downloaded bytes differ from reviewed material: {source['id']}")
        temporary.replace(destination)
        print("DOWNLOADED", source["id"], count, flush=True)
    (target / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
