"""CLI for the renderer-independent preview/comment contract."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videocut review", description="Versioned local preview review; render with the existing tools between prepare and publish")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("prepare", help="Record inputs before generating a new candidate")
    create.add_argument("workspace", type=Path)
    create.add_argument("--renderer", choices=["media", "codefilm"], required=True)
    create.add_argument("--config", type=Path, required=True)
    create.add_argument("--video", type=Path, required=True, help="Future candidate path; must not exist yet")
    create.add_argument("--timeline", type=Path, help="Actual renderer timeline; codefilm defaults to its input timeline")
    create.add_argument("--materials", type=Path, help="Resolved local materials list (media)")
    create.add_argument("--source", type=Path, action="append", default=[], help="Additional declared input file/directory")
    create.add_argument("--label", default="预览")
    create.add_argument("--width", type=int)
    create.add_argument("--height", type=int)
    create.add_argument("--offset", type=float, default=0, help="Global source time at preview frame zero")
    create.add_argument("--duration", type=float, help="Expected preview duration; codefilm defaults to remaining full timeline")
    for name in ("publish", "abandon", "state", "verify", "comments", "serve", "resolve", "comment"):
        command = sub.add_parser(name)
        command.add_argument("workspace", type=Path)
        if name == "publish":
            command.add_argument("--draft")
        elif name == "comments":
            command.add_argument("--claim", action="store_true", help="Atomically claim the next pending comment")
        elif name == "resolve":
            command.add_argument("--id", required=True)
            command.add_argument("--result-revision", required=True)
            command.add_argument("--note", required=True)
        elif name == "comment":
            command.add_argument("--revision", required=True)
            command.add_argument("--time", required=True, type=float)
            command.add_argument("--text", required=True)
            command.add_argument("--scene")
            command.add_argument("--region", nargs=4, type=float)
        elif name == "serve":
            command.add_argument("--port", type=int, default=4862)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = review.prepare(args.workspace, renderer=args.renderer, config=args.config,
                                    video=args.video, timeline=args.timeline, materials=args.materials,
                                    sources=args.source, label=args.label, width=args.width, height=args.height,
                                    offset=args.offset, duration=args.duration)
        elif args.command == "publish":
            result = review.publish(args.workspace, args.draft)
        elif args.command == "abandon":
            review.abandon(args.workspace)
            result = {"status": "abandoned"}
        elif args.command == "state":
            result = review.state(args.workspace)
        elif args.command == "verify":
            result = review.verify(args.workspace)
        elif args.command == "comments":
            result = review.comments(args.workspace, claim=args.claim)
        elif args.command == "comment":
            result = review.comment(args.workspace, revision_id=args.revision, time=args.time,
                                    text=args.text, scene_id=args.scene, region=args.region)
        elif args.command == "resolve":
            result = review.resolve(args.workspace, args.id, args.result_revision, args.note)
        else:
            from .review_server import create_server
            server = create_server(args.workspace, args.port)
            print(f"http://127.0.0.1:{server.server_port}/", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(f"review: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
