"""Project entry point for the pinned, unmodified ffmpeg-skill tools."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def skill_directory() -> Path:
    package = Path(__file__).resolve().parent
    for directory in (
        package.parent / ".agents/skills/ffmpeg-skill",
        package / "_vendor/ffmpeg_skill",
    ):
        if (directory / "SKILL.md").is_file():
            return directory
    raise RuntimeError("The bundled ffmpeg-skill is missing; restore the project files")


def main(argv: list[str] | None = None) -> int:
    directory = skill_directory()
    tools = sorted(
        path.stem
        for path in (directory / "scripts").glob("*.py")
        if not path.name.startswith("_")
    )
    parser = argparse.ArgumentParser(
        prog="videocut ffmpeg",
        description="Local ffmpeg-skill tools; use TOOL --help for upstream arguments",
    )
    parser.add_argument("--list", action="store_true", help="List available tools")
    parser.add_argument(
        "tool",
        nargs="?",
        default="list",
        choices=["list", "doctor", "contract", *tools],
    )
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.list or args.tool == "list":
        print("\n".join(["doctor", "contract", *tools]))
        return 0
    if args.tool in {"doctor", "contract"}:
        script = directory / "scripts/_contract.py"
        arguments = ["doctor"] if args.tool == "doctor" else []
    else:
        script = directory / "scripts" / f"{args.tool}.py"
        arguments = []
    # Keep the caller's cwd and argument boundaries: media paths, JSON, error codes,
    # timeouts and overwrite protection belong to the upstream tool.
    try:
        return subprocess.call(
            [sys.executable, str(script), *arguments, *args.arguments]
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
