"""Reuse the original 35-caption / nine-window acceptance on the new movie."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import verify_delivery
from videocut.codefilm import plan, verify_manifest

FILM = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--reference-mix", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    verify_manifest(args.render.resolve() / "render-manifest.json")
    coverage = json.loads((out / "edit-coverage.json").read_text())
    if coverage["source_hash"] != plan(FILM / "montage-codefilm.json")["source_hash"]:
        raise ValueError("The current edit no longer matches this delivery")
    cursor = 0
    for interval in coverage["coverage"]:
        if interval["a"] != cursor or interval["b"] <= cursor:
            raise ValueError("Delivery coverage is not continuous")
        cursor = interval["b"]
    if cursor != coverage["frames"] or cursor != 4100:
        raise ValueError("Delivery must cover exactly 4,100 frames")
    for src, dst in [(args.reference_mix.resolve(), out / "mix.wav"), (FILM / "data/timeline.json", out / "timeline.json")]:
        digest = lambda p: hashlib.file_digest(p.open("rb"), "sha256").hexdigest()
        if dst.exists():
            if digest(src) != digest(dst):
                raise ValueError(f"Reference changed: {dst}")
        else:
            os.link(src, dst)
    verify_delivery.OUT = out
    verify_delivery.main(final_name="杭州-山水与城市-实景混剪.mp4", manifest_name="edit-coverage.json")
    report_path = out / "verification.json"
    report = json.loads(report_path.read_text())
    report["schema"] = "hangzhou-montage-delivery-v1"
    report["visual_generation"]["real_media"] = "Reviewed Commons photographs, historical art and Tangxi footage; see montage-sources.json"
    report["edit_coverage"] = coverage
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
