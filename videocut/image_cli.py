"""CLI for generic image tools; platform workflows live in project skills."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .image_cards import plan_cards, render_cards, verify_cards
from .image_ops import preview_band, sample_frames
from .text_index import build_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videocut images",
                                     description="Generic frame sampling, text indexing and image cards")
    sub = parser.add_subparsers(dest="command", required=True)
    sample = sub.add_parser("sample", help="Extract exact candidates with aspect-preserving overview")
    sample.add_argument("source", type=Path)
    sample.add_argument("--output", type=Path, required=True)
    sample.add_argument("--at", type=float, action="append")
    sample.add_argument("--around", type=float, default=0)
    sample.add_argument("--count", type=int, default=12)
    band = sub.add_parser("band", help="Preview a horizontal pixel region without changing its text")
    band.add_argument("source", type=Path)
    band.add_argument("--output", type=Path, required=True)
    band.add_argument("--at", type=float, required=True)
    band.add_argument("--band", type=float, nargs=2, default=[0.76, 0.96])
    index = sub.add_parser("index", help="Normalize SRT/VTT/ASR JSON as a frame-search index")
    index.add_argument("track", type=Path)
    index.add_argument("--source", type=Path, required=True)
    index.add_argument("--output", type=Path, required=True)
    index.add_argument("--kind", choices=["platform", "asr", "user"], default="platform")
    index.add_argument("--generation", choices=["unspecified", "automatic", "human"], default="unspecified")
    index.add_argument("--language", default="unspecified")
    for command in ("plan", "render"):
        p = sub.add_parser(command, help="Read-only card plan" if command == "plan" else "Render image cards")
        p.add_argument("--manifest", type=Path, required=True)
        if command == "render":
            p.add_argument("--output", type=Path, required=True)
            p.add_argument("--resume", action="store_true")
            p.add_argument("--keep-going", action="store_true")
    verify = sub.add_parser("verify", help="Check actual image files, checksums and geometry")
    verify.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "sample":
            result = sample_frames(args.source, args.output, times=args.at,
                                   around=args.around, count=args.count)
        elif args.command == "band":
            result = preview_band(args.source, args.output, time=args.at, band=args.band)
        elif args.command == "index":
            result = build_index(args.track, args.source, args.output, kind=args.kind,
                                 generation=args.generation, language=args.language)
        elif args.command == "plan":
            result = plan_cards(args.manifest)
        elif args.command == "render":
            result = render_cards(args.manifest, args.output, resume=args.resume,
                                  keep_going=args.keep_going)
        else:
            result = verify_cards(args.report)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
